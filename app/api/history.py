from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import get_db
from app.api.auth import get_current_user
from app.models.models import Document, AnalysisResult
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class HistoryItemResponse(BaseModel):
    id: str
    filename: str
    created_at: datetime
    file_type: str
    analysis_status: str
    risk_level: str
    risks_count: int
    high_risk_count: int
    document_id: str

class HistoryResponse(BaseModel):
    items: List[HistoryItemResponse]
    total: int
    page: int
    limit: int
    total_pages: int

@router.get("/history", response_model=HistoryResponse)
async def get_document_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by success/error"),
    risk_level: Optional[str] = Query(None, description="Filter by overall risk level (high, medium, low)"),
    db: Session = Depends(get_db),
    user_data: dict = Depends(get_current_user)
):
    offset = (page - 1) * limit
    user_id = user_data["id"]
    
    # Base query joining Document and AnalysisResult for the specific user
    query = db.query(Document, AnalysisResult).outerjoin(
        AnalysisResult, Document.id == AnalysisResult.document_id
    ).filter(Document.user_id == user_id)
    
    # Apply filters
    if status_filter == "success":
        query = query.filter(AnalysisResult.success == True)
    elif status_filter == "error":
        query = query.filter(AnalysisResult.success == False)
        
    if risk_level:
        query = query.filter(AnalysisResult.overall_risk_level == risk_level)
        
    total_count = query.count()
    results = query.order_by(desc(Document.created_at)).offset(offset).limit(limit).all()
    
    history_items = []
    for doc, analysis in results:
        
        # Determine status string
        if analysis is None:
            a_status = "В очереди"
        elif analysis.success:
            a_status = "Успешно"
        else:
            a_status = "Ошибка"
            
        history_items.append(
            HistoryItemResponse(
                id=str(doc.id),
                filename=doc.original_name or doc.filename,
                created_at=doc.created_at,
                file_type=doc.file_type or "unknown",
                analysis_status=a_status,
                risk_level=analysis.overall_risk_level if analysis else "n/a",
                risks_count=analysis.total_risks if analysis else 0,
                high_risk_count=analysis.high_risk_count if analysis else 0,
                document_id=str(doc.id)
            )
        )
        
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
        
    return HistoryResponse(
        items=history_items,
        total=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages
    )


@router.get("/history/{document_id}", summary="Детали анализа документа")
async def get_document_analysis_details(
    document_id: str,
    db: Session = Depends(get_db),
    user_data: dict = Depends(get_current_user)
):
    """
    Возвращает полную сохраненную информацию по анализу договора.
    Используется для загрузки исторических отчетов на главной странице.
    """
    user_id = user_data["id"]
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
        
    analysis = db.query(AnalysisResult).filter(AnalysisResult.document_id == document_id, AnalysisResult.user_id == user_id).first()
    
    return {
        "file_info": {
            "filename": doc.original_name or doc.filename,
            "char_count": len(doc.extracted_text) if doc.extracted_text else 0,
            "extracted_text": doc.extracted_text,
            "file_type": doc.file_type
        },
        "analysis": {
            "document_type": analysis.document_type if analysis else "Неизвестный тип",
            "summary": analysis.summary if analysis else "Резюме отсутствует.",
            "overall_risk_level": analysis.overall_risk_level if analysis else "low",
            "risks": analysis.risks if (analysis and analysis.risks) else [],
            "recommendations": analysis.recommendations if (analysis and analysis.recommendations) else [],
            "success": analysis.success if analysis else True,
            "error_message": analysis.error_message if analysis else None
        }
    }


@router.delete("/history/{document_id}", summary="Удалить документ из истории")
async def delete_document_analysis(
    document_id: str,
    db: Session = Depends(get_db),
    user_data: dict = Depends(get_current_user)
):
    """
    Удаляет документ и все связанные с ним результаты анализа из базы данных.
    """
    user_id = user_data["id"]
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
        
    db.delete(doc)
    db.commit()
    return {"success": True, "message": "Документ успешно удален"}
