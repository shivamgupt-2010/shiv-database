from typing import List
from app.core.exceptions import AuthorizationError
from app.core.constants import RoleEnum

def verify_role(user_role: str, allowed_roles: List[str]) -> bool:
    """Verify if a user's role is in the list of allowed roles."""
    if user_role not in allowed_roles:
        raise AuthorizationError(f"Role '{user_role}' does not have permission to access this resource.")
    return True

def has_sufficient_role(user_role: str, required_role: str) -> bool:
    """
    Verify hierarchical roles. 
    SUPER_ADMIN > ADMIN > USER > GUEST
    """
    role_hierarchy = {
        RoleEnum.SUPER_ADMIN.value: 4,
        RoleEnum.ADMIN.value: 3,
        RoleEnum.USER.value: 2,
        RoleEnum.GUEST.value: 1,
    }
    
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 0)
    
    if user_level < required_level:
        raise AuthorizationError("Insufficient permissions.")
    return True
