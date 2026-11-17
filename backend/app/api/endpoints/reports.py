from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Chart, Report
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import ReportCreate, ReportUpdate
from app.services import export as export_service
from app.services.charts import _agg as chart_agg, _f as chart_f

logger = logging.getLogger("nexus")

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(user=Depends(get_current_user), db: Session = Depends(get_db)):
    reports = db.query(Report).order_by(Report.updated_at.desc()).all()
    return {"reports": [_r(r) for r in reports]}


@router.post("")
def create_report(payload: ReportCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = Report(project_id=payload.project_id, name=payload.name.strip(),
               description=payload.description, template=payload.template, sections=[])
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"report": _r(r)}


@router.get("/{report_id}")
def get_report(report_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise NotFoundError("Report not found.")
    return {"report": _r(r)}


@router.patch("/{report_id}")
def update_report(report_id: str, payload: ReportUpdate,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise NotFoundError("Report not found.")
    if payload.name is not None:
        r.name = payload.name.strip()
    if payload.description is not None:
        r.description = payload.description
    if payload.sections is not None:
        r.sections = payload.sections
        r.version += 1
    if payload.template is not None:
        r.template = payload.template
    db.commit()
    db.refresh(r)
    return {"report": _r(r)}


@router.delete("/{report_id}")
def delete_report(report_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise NotFoundError("Report not found.")
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.post("/{report_id}/preview")
def preview_report(report_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise NotFoundError("Report not found.")
    html = _render_sections(r.sections, db, user)
    return {"html": html}


@router.post("/{report_id}/export")
def export_report(report_id: str, fmt: str = "html", user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise NotFoundError("Report not found.")
    blocks = _render_sections(r.sections, db, user)
    report_meta = {"name": r.name, "generated_at": datetime.utcnow().isoformat()}
    if fmt == "pdf":
        path, fname = export_service.report_export_pdf(report_meta, blocks)
    else:
        path, fname = export_service.report_export_html(report_meta, blocks)
    return {"file": fname, "url": f"/api/export/download/{fname}", "format": fmt}


def _render_sections(sections: list, db: Session, user) -> list[str]:
    blocks = []
    for sec in sections:
        kind = sec.get("type", sec.get("kind", "paragraph"))
        content = sec.get("content") or sec.get("text") or ""
        if kind == "title":
            blocks.append(f"<h1>{content}</h1>")
        elif kind == "paragraph" or kind == "text":
            blocks.append(f"<p>{content}</p>")
        elif kind == "kpi":
            dataset_id = sec.get("dataset_id") or (sec.get("config") or {}).get("dataset_id")
            if dataset_id:
                try:
                    ds = get_dataset_for_user(db, dataset_id, user.id)
                except Exception as e:
                    logger.warning(f"Failed to get dataset for report: {e}")
                    ds = None
                if ds:
                    df = load_dataset_df(ds)
                    col = sec.get("column") or (sec.get("config") or {}).get("column")
                    agg = sec.get("aggregation") or (sec.get("config") or {}).get("aggregation", "sum")
                    if col and col in df.columns:
                        try:
                            val = chart_agg(df, col, agg)
                            blocks.append(f'<div class="kpi"><div class="v">{val:,.0f}</div><div class="l">{col} ({agg})</div></div>')
                        except Exception as e:
                            logger.warning(f"Failed to compute KPI: {e}")
                    else:
                        blocks.append(f'<div class="kpi"><div class="v">{len(df):,}</div><div class="l">rows</div></div>')
        elif kind == "chart":
            chart_id = sec.get("chart_id") or (sec.get("config") or {}).get("chart_id")
            if chart_id:
                c = db.query(Chart).filter(Chart.id == chart_id).first()
                if c and c.data and c.data.get("data"):
                    data = c.data["data"]
                    table = _chart_table(data)
                    if table:
                        blocks.append(table)
        elif kind == "table":
            dataset_id = sec.get("dataset_id") or (sec.get("config") or {}).get("dataset_id")
            columns = sec.get("columns") or (sec.get("config") or {}).get("columns") or []
            if dataset_id and columns:
                try:
                    ds = get_dataset_for_user(db, dataset_id, user.id)
                    df = load_dataset_df(ds)
                    cols = [c for c in columns if c in df.columns]
                    if cols:
                        sub = df[cols].head(100).fillna("")
                        blocks.append(sub.to_html(index=False, border=1, classes="nexus-table"))
                except Exception as e:
                    logger.warning(f"Failed to render table: {e}")
        elif kind == "ai_insight":
            blocks.append(f'<div class="block"><p>{content}</p></div>')
        else:
            blocks.append(f"<p>{content}</p>")
    return blocks


def _chart_table(data: dict) -> str | None:
    if "labels" in data and "values" in data:
        labels = data["labels"]
        values = data["values"]
        rows = "".join(f"<tr><td>{labels[i]}</td><td>{values[i]:,}</td></tr>" for i in range(min(len(labels), 30)))
        return f'<table><tr><th>Category</th><th>Value</th></tr>{rows}</table>'
    if "columns" in data and "rows" in data:
        header = "".join(f"<th>{c}</th>" for c in data["columns"])
        body = "".join("<tr>" + "".join(f"<td>{str(c)}</td>" for c in rw) + "</tr>" for rw in data["rows"][:50])
        return f"<table><tr>{header}</tr>{body}</table>"
    return None


def _r(r: Report) -> dict:
    return {
        "id": r.id, "name": r.name, "description": r.description, "sections": r.sections,
        "template": r.template, "project_id": r.project_id, "version": r.version,
        "is_favorite": r.is_favorite,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }