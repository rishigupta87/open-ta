import strawberry
from .queries import Query
from .mutations import Mutation


# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
