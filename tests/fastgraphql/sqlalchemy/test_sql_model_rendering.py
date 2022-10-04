from typing import Any, Type, Tuple, Optional, List, cast

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    ForeignKey,
    ARRAY,
)
from sqlalchemy.orm import relationship

from fastgraphql import FastGraphQL
from sqlalchemy.ext.declarative import declarative_base

from fastgraphql.exceptions import GraphQLFactoryException
from fastgraphql.schema import SelfGraphQL, GraphQLSchema
from fastgraphql.sqlalchemy import adapt_sqlalchemy_graphql
from fastgraphql.types import GraphQLDataType


expected_scalar_def = """
scalar DateTime
        """.strip()


@pytest.fixture(scope="function")
def fast_graphql() -> FastGraphQL:
    fast_graphql_ = FastGraphQL()
    return fast_graphql_


class TestSQLTypeRendering:
    def test_simple_type(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        @fast_graphql.type()
        class TypeWithoutReferences(Base):
            __tablename__ = "test"
            t_int = Column(Integer, primary_key=True)
            t_opt_int = Column(Integer, nullable=True)
            t_str = Column(String, nullable=False)
            t_opt_str = Column(String, nullable=True)
            t_float = Column(Float, nullable=False)
            t_opt_float = Column(Float, nullable=True)
            t_datatime = Column(DateTime, nullable=False)
            t_opt_datatime = Column(DateTime, nullable=True)
            t_boolean = Column(Boolean, nullable=False)
            t_opt_boolean = Column(Boolean, nullable=True)

        expected_graphql_def = """
type TypeWithoutReferences {
    t_int: Int!
    t_opt_int: Int
    t_str: String!
    t_opt_str: String
    t_float: Float!
    t_opt_float: Float
    t_datatime: DateTime!
    t_opt_datatime: DateTime
    t_boolean: Boolean!
    t_opt_boolean: Boolean
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeWithoutReferences)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

        assert (
            fast_graphql.render() == expected_scalar_def + "\n\n" + expected_graphql_def
        )

    def test_not_sql_model_exception(self) -> None:
        def parse_function(
            python_type_: Type[Any],
            exclude_model_attrs_: Optional[List[str]] = None,
            name_: Optional[str] = None,
        ) -> Tuple[GraphQLDataType, bool]:  # pragma: no cover
            ...

        class AnyClass:
            ...

        with pytest.raises(GraphQLFactoryException):
            adapt_sqlalchemy_graphql(
                python_type=AnyClass,
                schema=GraphQLSchema(),
                parse_type_func=parse_function,
                name=None,
                exclude_model_attrs=None,
                as_input=False,
            )

    def test_type_with_relationship(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        class TypeWithoutReferences(Base):
            __tablename__ = "test1"
            id = Column(Integer, primary_key=True)

        @fast_graphql.type()
        class TypeReference(Base):
            __tablename__ = "test2"
            id = Column(Integer, primary_key=True)
            reference_id = Column(Integer, ForeignKey("test1.id"), nullable=False)
            reference: TypeWithoutReferences = cast(
                TypeWithoutReferences, relationship("TypeWithoutReferences")
            )

        @fast_graphql.type()
        class TypeNullableReference(Base):
            __tablename__ = "test3"
            id = Column(Integer, primary_key=True)
            reference_id = Column(Integer, ForeignKey("test1.id"), nullable=True)
            reference: TypeWithoutReferences = cast(
                TypeWithoutReferences, relationship("TypeWithoutReferences")
            )

        expected_graphql_def = """
type TypeReference {
    id: Int!
    reference: TypeWithoutReferences!
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeReference)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

        expected_graphql_def = """
type TypeNullableReference {
    id: Int!
    reference: TypeWithoutReferences
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeNullableReference)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

    def test_excluded_attrs(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        @fast_graphql.type(exclude_model_attrs=["id"])
        class Model(Base):
            __tablename__ = "test"
            id = Column(Integer, primary_key=True)
            t_str = Column(String, nullable=False)

        expected_graphql_def = """
type Model {
    t_str: String!
}""".strip()
        self_graphql = SelfGraphQL.introspect(Model)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

    def test_type_with_foreign_key_only(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        class TypeWithoutReferences(Base):
            __tablename__ = "test1"
            id = Column(Integer, primary_key=True)

        @fast_graphql.type()
        class TypeReference(Base):
            __tablename__ = "test2"
            id = Column(Integer, primary_key=True)
            reference_id = Column(Integer, ForeignKey("test1.id"), nullable=False)

        @fast_graphql.type()
        class TypeNullableReference(Base):
            __tablename__ = "test3"
            id = Column(Integer, primary_key=True)
            reference_id = Column(Integer, ForeignKey("test1.id"), nullable=True)

        expected_graphql_def = """
type TypeReference {
    id: Int!
    reference_id: Int!
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeReference)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

        expected_graphql_def = """
type TypeNullableReference {
    id: Int!
    reference_id: Int
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeNullableReference)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

    def test_type_with_arrays(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        @fast_graphql.type()
        class TypeNonNullableArray(Base):
            __tablename__ = "test"
            t_int = Column(Integer, primary_key=True)
            t_array = Column(ARRAY(String), nullable=False)

        @fast_graphql.type()
        class TypeNullableArray(Base):
            __tablename__ = "test2"
            t_int = Column(Integer, primary_key=True)
            t_array = Column(ARRAY(String), nullable=True)

        expected_graphql_def = """
type TypeNonNullableArray {
    t_int: Int!
    t_array: [String!]!
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeNonNullableArray)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

        expected_graphql_def = """
type TypeNullableArray {
    t_int: Int!
    t_array: [String!]
} 
            """.strip()
        self_graphql = SelfGraphQL.introspect(TypeNullableArray)
        assert self_graphql
        assert self_graphql.as_type

        assert self_graphql.as_type.render() == expected_graphql_def

    def test_sql_type_as_query_input(self, fast_graphql: FastGraphQL) -> None:
        Base = declarative_base()  # type: Any
        fast_graphql.set_sqlalchemy_base(Base)

        @fast_graphql.input(name="ModelInput")
        class Model(Base):
            __tablename__ = "test"
            t_int = Column(Integer, primary_key=True)

        @fast_graphql.query()
        def simple_query(
            model: Model = fast_graphql.parameter(),
        ) -> Model:  # pragma: no cover
            ...

        expected_query_definition = """
simple_query(model: ModelInput!): Model!        
        """.strip()

        expected_graphql_definition = f"""
type Model {{
    t_int: Int!
}}

input ModelInput {{
    t_int: Int!
}}

type Query {{
    {expected_query_definition}
}}""".strip()

        self_graphql = SelfGraphQL.introspect(simple_query)
        assert self_graphql
        assert self_graphql.as_query
        assert self_graphql.as_query.render() == expected_query_definition
        assert fast_graphql.render() == expected_graphql_definition
