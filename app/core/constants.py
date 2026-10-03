from enum import Enum


class RoleEnum(str, Enum):
    USER = "user"
    ADMIN = "admin"
    DEVELOPER = "developer"
    SERVICE = "service"


class PermissionEnum(str, Enum):
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    DATABASE_READ = "database:read"
    DATABASE_WRITE = "database:write"
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_ADMIN = "project:admin"
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"


class ProviderTypeEnum(str, Enum):
    SHIV_NATIVE = "shiv_native"
    SUPABASE = "supabase"
    FIREBASE = "firebase"


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    BAD_REQUEST = "BAD_REQUEST"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class AuditEventType(str, Enum):
    USER_REGISTERED = "USER_REGISTERED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"

    RECORD_CREATED = "RECORD_CREATED"
    RECORD_READ = "RECORD_READ"
    RECORD_UPDATED = "RECORD_UPDATED"
    RECORD_DELETED = "RECORD_DELETED"
    RECORD_QUERIED = "RECORD_QUERIED"

    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"

    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"

    PROVIDER_ERROR = "PROVIDER_ERROR"
    AUTH_FAILURE = "AUTH_FAILURE"


# Default Role-Permission Mapping
DEFAULT_ROLE_PERMISSIONS = {
    RoleEnum.USER: [
        PermissionEnum.USER_READ,
        PermissionEnum.USER_WRITE,
        PermissionEnum.DATABASE_READ,
        PermissionEnum.DATABASE_WRITE,
        PermissionEnum.PROJECT_READ,
    ],
    RoleEnum.DEVELOPER: [
        PermissionEnum.USER_READ,
        PermissionEnum.USER_WRITE,
        PermissionEnum.DATABASE_READ,
        PermissionEnum.DATABASE_WRITE,
        PermissionEnum.PROJECT_READ,
        PermissionEnum.PROJECT_WRITE,
    ],
    RoleEnum.SERVICE: [
        PermissionEnum.DATABASE_READ,
        PermissionEnum.DATABASE_WRITE,
        PermissionEnum.PROJECT_READ,
        PermissionEnum.PROJECT_WRITE,
    ],
    RoleEnum.ADMIN: [
        PermissionEnum.USER_READ,
        PermissionEnum.USER_WRITE,
        PermissionEnum.DATABASE_READ,
        PermissionEnum.DATABASE_WRITE,
        PermissionEnum.PROJECT_READ,
        PermissionEnum.PROJECT_WRITE,
        PermissionEnum.PROJECT_ADMIN,
        PermissionEnum.ADMIN_USERS,
        PermissionEnum.ADMIN_SYSTEM,
    ],
}
