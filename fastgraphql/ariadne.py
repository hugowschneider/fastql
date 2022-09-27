from typing import List

from ariadne.asgi import GraphQL

from fastgraphql import FastGraphQL
from fastgraphql.utils import get_env_bool, FAST_GRAPHQL_DEBUG

try:
    from ariadne import (
        make_executable_schema as ariadne_make_executable_schema,
        MutationType,
        QueryType,
        SchemaBindable,
    )
except ImportError as e:
    raise ImportError(f"{e}.\nPlease use `pip install fastgraphql[ariadne]`")
from graphql import GraphQLSchema


def make_executable_schema(fast_graqhql: FastGraphQL) -> GraphQLSchema:
    mutation = MutationType()
    query = QueryType()
    bindables: List[SchemaBindable] = []
    if len(fast_graqhql.schema.queries):
        bindables.append(query)
        for name, query_ in fast_graqhql.schema.queries.items():
            if r := query_.resolver:
                query.set_field(name, r)

    if len(fast_graqhql.schema.mutations):
        bindables.append(mutation)
        for name, mutation_ in fast_graqhql.schema.mutations.items():
            if r := mutation_.resolver:
                mutation.set_field(name, r)

    return ariadne_make_executable_schema(fast_graqhql.render(), *bindables)


def make_graphql_asgi(fast_graqhql: FastGraphQL) -> GraphQL:
    return GraphQL(
        make_executable_schema(fast_graqhql),
        debug=get_env_bool(FAST_GRAPHQL_DEBUG, default_value=False),
    )
