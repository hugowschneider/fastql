from datetime import datetime
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Type,
    cast,
    Union,
    Callable,
    overload,
    TypeVar,
)

from pydantic import BaseModel

from fastgraphql.exceptions import GraphQLSchemaException

T_ANY = TypeVar("T_ANY")
T = TypeVar("T", bound=BaseModel)


class GraphQLTypeEngine:
    def render(self) -> str:
        raise NotImplementedError  # pragma: no cover


class GraphQLDataType(GraphQLTypeEngine):
    def __init__(self) -> None:
        super().__init__()

    def ref(self, nullable: bool = False) -> "GraphQLReference":
        raise NotImplementedError  # pragma: no cover


class GraphQLTypeAttribute:
    def __init__(self, name: str, attr_type: GraphQLDataType):
        self.name = name
        self.attr_type = attr_type

    def render(self) -> str:
        return f"{self.name}: {self.attr_type.render()}"


class GraphQLReference(GraphQLDataType):
    def __init__(self, reference: str, nullable: bool = False) -> None:
        super().__init__()
        self.reference = reference
        self.nullable = nullable

    def render(self) -> str:
        return f"{self.reference}{'' if self.nullable else '!'}"


class GraphQLType(GraphQLDataType):
    def __init__(
        self,
        name: str,
        python_type: Type[T],
        attrs: Optional[List[GraphQLTypeAttribute]] = None,
        as_input: bool = False,
    ):
        super().__init__()
        self.name = name
        if not attrs:
            attrs = []
        self.attrs = attrs
        self.as_input = as_input
        self.resolver = lambda attrs: python_type(**attrs)

    def add_attribute(self, field: GraphQLTypeAttribute) -> None:
        self.attrs.append(field)

    def ref(self, nullable: bool = False) -> GraphQLReference:
        return GraphQLReference(self.name, nullable=nullable)

    def render(self) -> str:
        separator = "\n    "
        decl = "input" if self.as_input else "type"
        return f"""
{decl} {self.name} {{
    {separator.join([attr.render() for attr in self.attrs])}
}}
        """.strip()


class GraphQLArray(GraphQLDataType):
    def __init__(self, item_type: GraphQLDataType):
        super().__init__()
        self.item_type = item_type

    def render(self) -> str:
        return f"[{self.item_type.render()}]"

    def ref(self, nullable: bool = False) -> GraphQLReference:
        return GraphQLReference(reference=self.render(), nullable=nullable)


class GraphQLScalar(GraphQLDataType):
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self._default_scalar = False
        self.encoder: Optional[Callable[..., Any]] = None
        self.decoder: Optional[Callable[..., Any]] = None

    def render(self) -> str:
        return f"scalar {self.name}"

    def ref(self, nullable: bool = False) -> GraphQLReference:
        return GraphQLReference(self.name, nullable=nullable)


class GraphQLBoolean(GraphQLScalar):
    def __init__(self) -> None:
        super().__init__("Boolean")
        self._default_scalar = True


class GraphQLInteger(GraphQLScalar):
    def __init__(self) -> None:
        super().__init__("Int")
        self._default_scalar = True


class GraphQLString(GraphQLScalar):
    def __init__(self) -> None:
        super().__init__("String")
        self._default_scalar = True


class GraphQLFloat(GraphQLScalar):
    def __init__(self) -> None:
        super().__init__("Float")
        self._default_scalar = True


class GraphQLID(GraphQLScalar):
    def __init__(self) -> None:
        super().__init__("ID")
        self._default_scalar = True


class GraphQLDateTime(GraphQLScalar):
    def __init__(self, date_time_format: str) -> None:
        super().__init__("DateTime")

        def encoder(s: datetime) -> str:
            return s.strftime(date_time_format)

        def decoder(s: str) -> datetime:
            return datetime.strptime(s, date_time_format)

        self.encoder = encoder
        self.decoder = decoder


class GraphQLDate(GraphQLScalar):
    def __init__(self, date_format: str) -> None:
        super().__init__("Date")
        self.encoder = lambda x: x.strftime(date_format)
        self.decoder = lambda x: datetime.strptime(x, date_format).date()


class GraphQLTime(GraphQLScalar):
    def __init__(self, time_format: str) -> None:
        super().__init__("Time")
        self.encoder = lambda x: x.strftime(time_format)
        self.decoder = lambda x: datetime.strptime(x, time_format).time()


class InjectedFunctionParameter:
    def __init__(self, name: Optional[str] = None):
        self.resolver: Optional[Callable[..., Any]] = None
        self.name = name

    def resolve(self, input: Any) -> Any:
        if r := self.resolver:
            return r(input)
        return input


class GraphQLFunctionField(GraphQLTypeEngine, InjectedFunctionParameter):
    def __init__(
        self, graphql_type: Optional[GraphQLDataType] = None, name: Optional[str] = None
    ):
        super().__init__(name=name)
        self.type = graphql_type
        self.python_name: str = ""

    def set_name(self, name: str) -> None:
        self.name = name

    def set_python_name(self, python_name: str) -> None:
        self.python_name = python_name

    def render(self) -> str:
        assert self.type
        return f"{self.name}: {self.type.render()}"


class GraphQLQueryField(GraphQLFunctionField):
    ...


class GraphQLFunction(GraphQLTypeEngine):
    def __init__(
        self,
        name: str,
        return_type: GraphQLDataType,
        parameters: Optional[List[GraphQLFunctionField]] = None,
    ):
        self.name = name
        self.return_type = return_type
        self.parameters: List[GraphQLFunctionField] = parameters if parameters else []
        self.resolver: Optional[Callable[..., T_ANY]] = None
        self.injected_parameters: List[InjectedFunctionParameter] = []

    def add_parameter(self, parameter: GraphQLFunctionField) -> None:
        self.parameters.append(parameter)

    def add_injected_parameter(self, parameter: InjectedFunctionParameter) -> None:
        self.injected_parameters.append(parameter)

    def render(self) -> str:
        parameters = ", ".join([p.render() for p in self.parameters])
        if parameters:
            parameters = f"({parameters})"
        return f"{self.name}{parameters}: {self.return_type.render()}"


class GraphQLSchema(GraphQLTypeEngine):
    def __init__(self) -> None:
        self.types: Dict[str, GraphQLType] = {}
        self.scalars: Dict[str, GraphQLScalar] = {}
        self.inputs: Dict[str, GraphQLType] = {}
        self.queries: Dict[str, GraphQLFunction] = {}
        self.mutations: Dict[str, GraphQLFunction] = {}

    def check_type_name_conflict(
        self, graphql_type: Union[GraphQLType, GraphQLScalar]
    ) -> None:
        if graphql_type.name in self.inputs:
            raise GraphQLSchemaException(
                f"Name {graphql_type.name} is already used as an input. Please specify another name!"
            )
        if graphql_type.name in self.types:
            raise GraphQLSchemaException(
                f"Name {graphql_type.name} is already used as an type. Please specify another name!"
            )
        if graphql_type.name in self.scalars and not isinstance(
            graphql_type, GraphQLScalar
        ):
            raise GraphQLSchemaException(
                f"Name {graphql_type.name} is already used as an scalar. Please specify another name!"
            )

    def check_function_name_conflict(self, graphql_type: GraphQLFunction) -> None:
        if graphql_type.name in self.queries:
            raise GraphQLSchemaException(
                f"Name {graphql_type.name} is already used for a query. Please specify another name!"
            )
        if graphql_type.name in self.mutations:
            raise GraphQLSchemaException(
                f"Name {graphql_type.name} is already used for a mutation. Please specify another name!"
            )

    def add_type(self, graphql_type: GraphQLType) -> None:
        self.check_type_name_conflict(graphql_type=graphql_type)
        self.types[graphql_type.name] = graphql_type

    def add_scalar(self, graphql_type: GraphQLScalar) -> None:
        self.check_type_name_conflict(graphql_type=graphql_type)
        self.scalars[graphql_type.name] = graphql_type

    def add_input_type(self, graphql_type: GraphQLType) -> None:
        self.check_type_name_conflict(graphql_type=graphql_type)
        self.inputs[graphql_type.name] = graphql_type

    def render(self) -> str:
        separator = "\n\n"
        GT = Union[GraphQLType, GraphQLScalar]

        def sort_and_write(types: Iterable[GT]) -> str:
            sorted_types = sorted(types, key=lambda x: x.name)
            return separator.join([s.render() for s in sorted_types])

        def sort_and_write_functions(
            functions: Iterable[GraphQLFunction], as_mutation: bool
        ) -> str:
            if not any(functions):
                return ""
            decl = "Mutation" if as_mutation else "Query"
            sorted_types = sorted(functions, key=lambda x: x.name)
            queries_str = "\n\t".join([s.render() for s in sorted_types])
            return f"""
type {decl} {{
    {queries_str}
}}""".strip()

        s = separator.join(
            s
            for s in [
                sort_and_write(cast(Iterable[GT], self.scalars.values())),
                sort_and_write(cast(Iterable[GT], self.types.values())),
                sort_and_write(cast(Iterable[GT], self.inputs.values())),
                sort_and_write_functions(
                    cast(Iterable[GraphQLFunction], self.queries.values()), False
                ),
                sort_and_write_functions(
                    cast(Iterable[GraphQLFunction], self.mutations.values()), True
                ),
            ]
            if len(s)
        )
        return s

    def add_query(self, graphql_query: GraphQLFunction) -> None:
        self.check_function_name_conflict(graphql_query)
        self.queries[graphql_query.name] = graphql_query

    def add_mutation(self, graphql_mutation: GraphQLFunction) -> None:
        self.check_function_name_conflict(graphql_mutation)
        self.mutations[graphql_mutation.name] = graphql_mutation


class SelfGraphQL:
    @staticmethod
    @overload
    def introspect(type_: Type[Any]) -> Optional["SelfGraphQLType"]:
        ...

    @staticmethod
    @overload
    def introspect(type_: Callable[..., Any]) -> Optional["SelfGraphQLFunction"]:
        ...

    @staticmethod
    def introspect(
        type_: Union[Type[Any], Callable[..., Any]]
    ) -> Union["SelfGraphQL", None]:
        if hasattr(type_, "__graphql__"):
            return cast(SelfGraphQL, getattr(type_, "__graphql__"))
        return None


class SelfGraphQLType(SelfGraphQL):
    def __init__(self) -> None:
        self.as_type: Optional[GraphQLType] = None
        self.as_input: Optional[GraphQLType] = None


class SelfGraphQLFunction(SelfGraphQL):
    def __init__(self) -> None:
        self.as_query: Optional[GraphQLFunction] = None
        self.as_mutation: Optional[GraphQLFunction] = None
