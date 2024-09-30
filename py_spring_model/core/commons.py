from py_spring import Properties
from pydantic import BaseModel, ConfigDict


class ApplicationFileGroups(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    class_files: set[str]
    model_files: set[str]


class PySpringModelProperties(Properties):
    __key__ = "py_spring_model"
    model_file_postfix_patterns: set[str]
    sqlalchemy_database_uri: str
