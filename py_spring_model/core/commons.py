from py_spring_core import Properties


class PySpringModelProperties(Properties):
    """
    A class that extends the `Properties` class from the `py_spring_core` module.
    This class defines properties specific to the PySpring Model, including:

    - `__key__`: The key used to identify this set of properties.
    - `sqlalchemy_database_uri`: The SQLAlchemy database URI used for the model.
    """

    __key__ = "py_spring_model"
    sqlalchemy_database_uri: str
    create_all_tables: bool = True
    create_crud_routes: bool = False
