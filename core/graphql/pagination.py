from functools import wraps
import graphene
from django.core.paginator import Paginator, EmptyPage

class PaginationInput(graphene.InputObjectType):
    page = graphene.Int(default_value=1)
    page_size = graphene.Int(default_value=20)

class PaginationInfo(graphene.ObjectType):
    page = graphene.Int()
    page_size = graphene.Int()
    total_pages = graphene.Int()
    total_count = graphene.Int()
    has_next = graphene.Boolean()
    has_previous = graphene.Boolean()

def paginated_field(object_type, default_page_size=20):
    """
    Decorator to add pagination to any list field
    """
    class PaginatedResult(graphene.ObjectType):
        items = graphene.List(object_type)
        pagination = graphene.Field(PaginationInfo)
    
    def decorator(resolve_func):
        @wraps(resolve_func)
        def wrapper(root, info, pagination=None, **kwargs):
            queryset = resolve_func(root, info, **kwargs)
            
            page = 1
            page_size = default_page_size
            
            if pagination is not None:
                page = getattr(pagination, 'page', None) or 1
                page_size = getattr(pagination, 'page_size', None) or default_page_size
            
            paginator = Paginator(queryset, page_size)
            
            if paginator.count == 0:
                return PaginatedResult(
                    items=[],
                    pagination=PaginationInfo(
                        page=1, page_size=page_size, total_pages=0,
                        total_count=0, has_next=False, has_previous=False
                    )
                )
            
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)
            
            pagination_info = PaginationInfo(
                page=page_obj.number,
                page_size=page_size,
                total_pages=paginator.num_pages,
                total_count=paginator.count,
                has_next=page_obj.has_next(),
                has_previous=page_obj.has_previous()
            )
            
            return PaginatedResult(
                items=list(page_obj.object_list),
                pagination=pagination_info
            )
        
        return wrapper
    return decorator
