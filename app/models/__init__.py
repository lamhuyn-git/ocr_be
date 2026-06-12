"""Import all models so Base.metadata is fully populated (alembic, create_all)."""
from app.models.user import User, RefreshToken  # noqa: F401
from app.models.province import Province  # noqa: F401
from app.models.organization import Organization, OrganizationMember, OrgRole  # noqa: F401
from app.models.form import (  # noqa: F401
    FormType, FormTemplate, Form, DetailForm, ExtractedResult, HistoryContent,
    FormStatus, FormStatusHistory, REVIEW_PREDECESSORS,
)
from app.models.citizen import (  # noqa: F401
    Citizen, CitizenRelation,
    Gender, MaritalStatus, ResidenceStatus, LifeStatus, RelationType,
)
from app.models.residence import (  # noqa: F401
    TemporaryResidence, TempResidenceStatus,
)
