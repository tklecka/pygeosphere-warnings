"""Exceptions for the GeoSphere Austria Warn API client."""


class GeoSphereWarningsError(Exception):
    """Base exception for the GeoSphere Austria Warn API."""


class GeoSphereConnectionError(GeoSphereWarningsError):
    """Raised when communication with the API fails."""


class GeoSphereApiError(GeoSphereWarningsError):
    """Raised when the API returns an unexpected response."""


class GeoSphereMunicipalityNotFoundError(GeoSphereApiError):
    """Raised when no Austrian municipality exists for the given coordinates."""
