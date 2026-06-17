"""Schemas cho domain form — tách theo model. Re-export để giữ `from app.schemas.form import X`."""
from app.schemas.form.form_type import (  # noqa: F401
    FormTypeCreate, FormTypeUpdate, FormTypeResponse,
)
from app.schemas.form.form_template import (  # noqa: F401
    FormTemplateUpdate, FormTemplateResponse,
)
from app.schemas.form.evidence import (  # noqa: F401
    EvidenceInput, EvidenceCreate, EvidenceUpdate, EvidenceResponse,
)
from app.schemas.form.tamtru_form import (  # noqa: F401
    TamtruFormInput, TamtruFormCreate, TamtruFormUpdate, TamtruFormResponse,
)
from app.schemas.form.form_result import (  # noqa: F401
    FormResultCreate, FormResultUpdate, FormResultResponse, FormResultConfirmRequest,
)
from app.schemas.form.form import (  # noqa: F401
    FormCreate, FormDraftCreate, FormDraftUpdate, FormTransitionRequest,
    FormCreateResponse, FormResponse, FormDetailResponse, FormList, FormExtractResponse,
)

__all__ = [
    "FormTypeCreate", "FormTypeUpdate", "FormTypeResponse",
    "FormTemplateUpdate", "FormTemplateResponse",
    "EvidenceInput", "EvidenceCreate", "EvidenceUpdate", "EvidenceResponse",
    "TamtruFormInput", "TamtruFormCreate", "TamtruFormUpdate", "TamtruFormResponse",
    "FormResultCreate", "FormResultUpdate", "FormResultResponse", "FormResultConfirmRequest",
    "FormCreate", "FormDraftCreate", "FormDraftUpdate", "FormTransitionRequest",
    "FormCreateResponse", "FormResponse", "FormDetailResponse", "FormList", "FormExtractResponse",
]
