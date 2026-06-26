from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user, get_current_superuser
from app.database import get_db
from app.models.form import FormType, FormTemplate
from app.models.user import User
from app.schemas.form import FormTemplateUpdate, FormTemplateResponse
from app.services.form_service import save_file, validate_template_yaml
from app.services import s3_service

router = APIRouter(prefix="/form-templates", tags=["FormTemplate"])


async def _deactivate_actives(db: AsyncSession, form_type_id: UUID, exclude_id: UUID | None = None) -> None:
    query = select(FormTemplate).where(
        FormTemplate.form_type_id == form_type_id, FormTemplate.is_active == True  # noqa: E712
    )
    if exclude_id is not None:
        query = query.where(FormTemplate.id != exclude_id)
    for t in (await db.execute(query)).scalars().all():
        t.is_active = False


@router.post("", response_model=FormTemplateResponse, status_code=status.HTTP_201_CREATED, summary="Upload a template version")
async def create_template(
    form_type_id: UUID,
    name: str,
    version: str,
    config_file: UploadFile = File(..., description="YAML config"),
    template_file: UploadFile = File(..., description="URL file Word template (.docx) để user download & điền"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(FormType, form_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")
    if not config_file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config must be .yaml/.yml")
    yaml_bytes = await config_file.read()

    try:
        validate_template_yaml(yaml_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid template config: {exc}")

    if not template_file.filename.endswith(".docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Template file must be .docx",)
    template_bytes = await template_file.read()

    config_path = save_file("yaml", name, version, "yaml", yaml_bytes, "application/yaml",)
    template_path = save_file("docx", name, version, "docx", template_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document",)

    await _deactivate_actives(db, form_type_id)

    template = FormTemplate(
        form_type_id=form_type_id, 
        name=name, 
        version=version,
        config_path=config_path, 
        template_url= template_path,
        is_active=True, 
        created_by=current_user.id
    )

    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.get("", response_model=list[FormTemplateResponse], summary="List templates (filter by form_type_id)")
async def list_templates(
    form_type_id: UUID | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(FormTemplate)
    if form_type_id is not None:
        query = query.where(FormTemplate.form_type_id == form_type_id)
    rows = (await db.execute(query.order_by(FormTemplate.created_at.desc()))).scalars().all()
    return list(rows)


# @router.get("/{template_id}", response_model=FormTemplateResponse, summary="Get a template")
# async def get_template(
#     template_id: UUID,
#     _: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     template = await db.get(FormTemplate, template_id)
#     if not template:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
#     return template


@router.patch("/{template_id}", response_model=FormTemplateResponse, summary="Update a template (metadata / activate)")
async def update_template(
    template_id: UUID,
    body: FormTemplateUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    fields = model_dump(exclude_unset=True)
    # Bật active bản này → tắt các bản active khác cùng form_type (giữ 1 active/loại)
    if fields.get("is_active") is True:
        await _deactivate_actives(db, template.form_type_id, exclude_id=template.id)
    for field, value in fields.items():
        setattr(template, field, value)
    await db.flush()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", summary="Delete a template")
async def delete_template(
    template_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(FormTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    await db.delete(template)
    await db.flush()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Deleted template successfully"})


@router.get("/download")
async def download_template( form_name : str, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),):  
    print("form_name =", form_name)
    result = await db.execute(
        select(FormTemplate.template_url)
        .join(FormType, FormTemplate.form_type_id == FormType.id,)
        .where(
            and_(func.lower(FormType.type_name) == form_name, FormTemplate.is_active.is_(True),)
        )
    )

    template_url = result.scalar_one_or_none()

    if not template_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Không tìm thấy file mẫu.",)

    key = s3_service.key_from_path_url(template_url)

    download_url = s3_service.generate_presigned_download(key=key,filename="Mau_CT01.docx",)

    return {
        "download_url": download_url
    }
