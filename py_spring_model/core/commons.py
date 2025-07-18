from py_spring_core import Properties
from pydantic import BaseModel, ConfigDict


class ApplicationFileGroups(BaseModel):
    """
    A Pydantic model that defines the file groups for a PySpring application.

    The `ApplicationFileGroups` model has the following attributes:

    - `class_files`: A set of strings representing the class files for the application.
    - `model_files`: A set of strings representing the model files for the application.
    """

    model_config = ConfigDict(protected_namespaces=())
    class_files: set[str]
    model_files: set[str]


class PySpringModelProperties(Properties):
    """
    A class that extends the `Properties` class from the `py_spring_core` module.
    This class defines properties specific to the PySpring Model, including:

    - `__key__`: The key used to identify this set of properties.
    - `model_file_postfix_patterns`: A set of strings representing file name patterns for model files.
    - `sqlalchemy_database_uri`: The SQLAlchemy database URI used for the model.
    - `create_all_tables`: Whether to automatically create all tables on startup.
    - `prevent_duplicate_imports`: Whether to prevent duplicate model imports and clean registry conflicts.
    """

    __key__ = "py_spring_model"
    model_file_postfix_patterns: set[str]
    sqlalchemy_database_uri: str
    create_all_tables: bool = True
    prevent_duplicate_imports: bool = True
