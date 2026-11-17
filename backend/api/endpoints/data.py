from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io

router = APIRouter()

@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(('.csv', '.json', '.parquet')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    contents = await file.read()
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(contents))
        elif file.filename.endswith('.parquet'):
            df = pd.read_parquet(io.BytesIO(contents))
            
        profile = {
            "filename": file.filename,
            "rows": len(df),
            "columns": len(df.columns),
            "columns_info": []
        }
        
        for col in df.columns:
            col_info = {
                "name": col,
                "type": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "unique_count": int(df[col].nunique())
            }
            if pd.api.types.is_numeric_dtype(df[col]):
                col_info.update({
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None
                })
            profile["columns_info"].append(col_info)
            
        return {"status": "success", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
