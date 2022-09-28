import functools
import logging

from fastgraphql.factory import GraphQLTypeFactory, GraphQLFunctionFactory, _DateFormats

from typing import (
    Type,
    TypeVar,
    Optional,
    Callable,
    List,
    Any,
    Tuple,
    Dict,
)
from pydantic import BaseModel

from fastgraphql.schema import (
    GraphQLSchema,
    GraphQLType,
    GraphQLFunction,
    GraphQLQueryField,
    GraphQLScalar,
)

T = TypeVar("T", bound=BaseModel)
T_ANY = TypeVar("T_ANY")


class FastGraphQL:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        time_format = "%H:%M:%S"
        date_format = "%Y-%m-%d"
        self._date_formats = _DateFormats(
            date_format=date_format,
            time_format=time_format,
            date_time_format=f"{date_format}T{time_format}%z",
        )
        self.schema = GraphQLSchema()
        self.type_factory = GraphQLTypeFactory(
            schema=self.schema, input_factory=False, date_formats=self._date_formats
        )
        self.input_factory = GraphQLTypeFactory(
            schema=self.schema, input_factory=True, date_formats=self._date_formats
        )
        self.query_factory = GraphQLFunctionFactory(
            schema=self.schema,
            mutation_factory=False,
            input_factory=self.input_factory,
            type_factory=self.type_factory,
        )
        self.mutation_factory = GraphQLFunctionFactory(
            schema=self.schema,
            mutation_factory=True,
            input_factory=self.input_factory,
            type_factory=self.type_factory,
        )

    def get_date_format(self) -> str:
        return self._date_formats.date_format

    def get_time_format(self) -> str:
        return self._date_formats.time_format

    def get_date_time_format(self) -> str:
        return self._date_formats.date_time_format

    def set_date_format(self, date_format: str) -> None:
        self._date_formats.date_format = date_format

    def set_time_format(self, time_format: str) -> None:
        self._date_formats.time_format = time_format

    def set_date_time_format(self, date_time_format: str) -> None:
        self._date_formats.date_time_format = date_time_format

    def render(self) -> str:
        return self.schema.render()

    def _graphql_model(
        self,
        exclude_model_attrs: Optional[List[str]],
        name: Optional[str],
        as_input: bool,
    ) -> Callable[..., Type[T]]:
        if exclude_model_attrs is None:
            exclude_model_attrs = []

        def decorator(python_type: Type[T]) -> Type[T]:
            self.logger.info(
                f"Constructing GraphQL {'input' if as_input else 'type'} for {python_type.__qualname__}"
            )
            if as_input:
                factory = self.input_factory
            else:
                factory = self.type_factory

            graphql_type, _ = factory.create_graphql_type(
                python_type=python_type,
                name=name,
                exclude_model_attrs=exclude_model_attrs,
            )
            if not isinstance(graphql_type, GraphQLType):  # pragma: no cover
                raise Exception("Something went wrong")

            return python_type

        return decorator

    def graphql_type(
        self,
        exclude_model_attrs: Optional[List[str]] = None,
        name: Optional[str] = None,
    ) -> Callable[..., Type[T]]:
        return self._graphql_model(
            exclude_model_attrs=exclude_model_attrs, name=name, as_input=False
        )

    def graphql_input(
        self,
        exclude_model_attrs: Optional[List[str]] = None,
        name: Optional[str] = None,
    ) -> Callable[..., Type[T]]:
        return self._graphql_model(
            exclude_model_attrs=exclude_model_attrs, name=name, as_input=True
        )

    def graphql_query(
        self,
        name: Optional[str] = None,
    ) -> Callable[..., Callable[..., T_ANY]]:
        return self._graphql_function(name=name, as_mutation=False)

    def graphql_mutation(
        self,
        name: Optional[str] = None,
    ) -> Callable[..., Callable[..., T_ANY]]:
        return self._graphql_function(name=name, as_mutation=True)

    def _graphql_function(
        self,
        name: Optional[str],
        as_mutation: bool,
    ) -> Callable[..., Callable[..., T_ANY]]:
        def decorator(func: Callable[..., T_ANY]) -> Callable[..., T_ANY]:
            self.logger.info(
                f"Constructing GraphQL {'input' if False else 'query'} for {func.__qualname__}"
            )
            if as_mutation:
                graphql_type = self.mutation_factory.create_function(
                    func=func, name=name
                )
                self.schema.add_mutation(graphql_type)
            else:
                graphql_type = self.query_factory.create_function(func=func, name=name)
                self.schema.add_query(graphql_type)

            if not isinstance(graphql_type, GraphQLFunction):  # pragma: no cover
                raise Exception("Something went wrong")

            @functools.wraps(func)
            def _decorator(*args: Tuple[Any], **kwargs: Dict[str, Any]) -> T_ANY:
                resolved_kwargs: Dict[str, Any] = {}
                for parameter in graphql_type.parameters:
                    python_name = parameter.python_name
                    name = parameter.name
                    assert python_name
                    assert name
                    value = kwargs[name]
                    resolved_kwargs[python_name] = (
                        parameter.resolve(value) if value is not None else None
                    )

                return func(**resolved_kwargs)

            graphql_type.resolver = _decorator

            return _decorator

        return decorator

    def graphql_query_field(
        self, name: Optional[str] = None, graphql_scalar: Optional[GraphQLScalar] = None
    ) -> Any:
        return GraphQLQueryField(name=name, graphql_type=graphql_scalar)
