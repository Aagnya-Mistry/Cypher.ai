from functools import lru_cache
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from app.agents.agent3.pipeline import Agent3RiskScoringPipeline
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, require_hardcoded_user
from app.schemas.agent3 import Agent3FinalReport, Agent3ScoreDomainRequest, DomainScoreResult
from app.services.agent3_store_service import Agent3ScoreStore
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix='/agent3', tags=['Agent 3 - Risk Scoring'])


@lru_cache
def get_agent3_pipeline() -> Agent3RiskScoringPipeline:
    settings = get_settings()
    return Agent3RiskScoringPipeline(
        knowledge_base=KnowledgeBaseService(knowledge_base_path=settings.knowledge_base_path),
        store=Agent3ScoreStore(store_path=settings.agent3_store_path),
    )


@router.post('/score-domain', response_model=DomainScoreResult)
def score_domain(
    payload: Agent3ScoreDomainRequest,
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    pipeline: Agent3RiskScoringPipeline = Depends(get_agent3_pipeline),
) -> DomainScoreResult:
    try:
        return pipeline.score_domain(
            user_id=user.username,
            report_name=payload.report_name,
            agent2_result=payload.agent2_result,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Agent 3 domain scoring failed: {exc}',
        ) from exc


@router.get('/report', response_model=Agent3FinalReport)
def get_report(
    report_name: str = Query(..., min_length=1),
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    pipeline: Agent3RiskScoringPipeline = Depends(get_agent3_pipeline),
) -> Agent3FinalReport:
    try:
        return pipeline.generate_report(user_id=user.username, report_name=report_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Agent 3 report generation failed: {exc}',
        ) from exc


@router.get('/report/excel')
def download_report_excel(
    report_name: str = Query(..., min_length=1),
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    pipeline: Agent3RiskScoringPipeline = Depends(get_agent3_pipeline),
) -> StreamingResponse:
    try:
        report = pipeline.generate_report(user_id=user.username, report_name=report_name)
        header, rows = pipeline.build_excel_rows(report)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Agent 3 Excel generation failed: {exc}',
        ) from exc

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Domain Scores'

    worksheet.append(header)
    for row in rows:
        worksheet.append(row)

    worksheet_summary = workbook.create_sheet(title='Summary')
    worksheet_summary.append(['Report Name', report.report_name])
    worksheet_summary.append(['Generated At', report.generated_at])
    worksheet_summary.append(['Total Domains Scored', str(report.total_domains_scored)])
    worksheet_summary.append(['Aggregate Score', f'{report.aggregate_score:.4f}'])
    worksheet_summary.append(['Average Threshold', f'{report.average_threshold:.4f}'])
    worksheet_summary.append(['Domains Meeting Threshold', str(report.domains_meeting_threshold)])
    worksheet_summary.append(['Domains Below Threshold', str(report.domains_below_threshold)])
    worksheet_summary.append(['Overall Status', report.overall_status])

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f'{report_name}_agent3_risk_report.xlsx'
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    return StreamingResponse(
        buffer,
        headers=headers,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
