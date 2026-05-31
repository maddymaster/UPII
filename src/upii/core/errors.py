class UPIIError(Exception):
    """Base class for all UPII exceptions."""
    pass

class IngestionError(UPIIError):
    """Raised when file ingestion fails."""
    pass

class StorageError(UPIIError):
    """Raised when database or vector store operations fail."""
    pass

class ModelError(UPIIError):
    """Raised when local inference fails."""
    pass
