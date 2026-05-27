# Routing Conventions

> **TL;DR**: All routes follow RESTful patterns. Use blueprints for organization. Return consistent JSON responses.

## URL Structure

```
/api/v1/<resource>
/api/v1/<resource>/:id
/api/v1/<resource>/:id/<related>
```

### ✅ GOOD - RESTful routes

```python
# In routes/articles.py
@bp.route('/articles', methods=['GET'])
def list_articles():
    """List all articles with pagination."""
    # ...

@bp.route('/articles', methods=['POST'])
def create_article():
    """Create a new article."""
    # ...

@bp.route('/articles/<int:article_id>', methods=['GET'])
def get_article(article_id: int):
    """Get a single article by ID."""
    # ...

@bp.route('/articles/<int:article_id>', methods=['PUT'])
def update_article(article_id: int):
    """Update an existing article."""
    # ...

@bp.route('/articles/<int:article_id>', methods=['DELETE'])
def delete_article(article_id: int):
    """Delete an article."""
    # ...
```

### ❌ BAD - Non-RESTful routes

```python
@bp.route('/get_article')
def get_article():
    # ...

@bp.route('/article_create')
def article_create():
    # ...
```

## Blueprint Organization

### ✅ GOOD - Organized blueprints

```python
# api/v1/articles.py
from flask import Blueprint, jsonify, request

articles_bp = Blueprint('articles', __name__, url_prefix='/api/v1/articles')


@articles_bp.route('', methods=['GET'])
def list_articles():
    """List articles with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    articles = Article.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'data': [a.to_dict() for a in articles.items],
        'pagination': {
            'page': articles.page,
            'per_page': articles.per_page,
            'total': articles.total,
            'pages': articles.pages,
        }
    })
```

### Registering blueprints

```python
# app.py
from api.v1.articles import articles_bp
from api.v1.auth import auth_bp

app.register_blueprint(articles_bp)
app.register_blueprint(auth_bp)
```

## Response Format

### ✅ GOOD - Consistent JSON responses

```python
from flask import jsonify


def success_response(data: Any, status_code: int = 200) -> tuple[Any, int]:
    """Return a successful JSON response."""
    return jsonify({
        'success': True,
        'data': data,
    }), status_code


def error_response(message: str, status_code: int = 400) -> tuple[dict, int]:
    """Return an error JSON response."""
    return jsonify({
        'success': False,
        'error': message,
    }), status_code


@articles_bp.route('/articles/<int:article_id>', methods=['GET'])
def get_article(article_id: int):
    article = Article.query.get(article_id)
    if not article:
        return error_response('Article not found', 404)
    return success_response(article.to_dict())
```

### ❌ BAD - Inconsistent response formats

```python
@articles_bp.route('/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    article = Article.query.get(article_id)
    if not article:
        return 'Not found', 404  # String response
    return article.to_dict()  # Dict response (not JSON)
```

## Request Validation

### ✅ GOOD - Use Pydantic for request validation

```python
from pydantic import BaseModel, Field
from flask import request


class CreateArticleRequest(BaseModel):
    """Request model for creating an article."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: int = Field(..., gt=0)
    published: bool = False


@articles_bp.route('/articles', methods=['POST'])
def create_article():
    """Create a new article."""
    try:
        data = CreateArticleRequest.model_validate(request.json)
    except ValidationError as e:
        return error_response(str(e), 400)
    
    article = Article(
        title=data.title,
        content=data.content,
        author_id=data.author_id,
        published=data.published,
    )
    db.session.add(article)
    db.session.commit()
    
    return success_response(article.to_dict(), 201)
```

## Error Handling

### ✅ GOOD - Centralized error handlers

```python
# api/v1/errors.py
from flask import jsonify


class APIError(Exception):
    """Base API error."""
    status_code = 400
    
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__()
        self.message = message
        self.status_code = status_code or self.status_code


class NotFoundError(APIError):
    """Resource not found."""
    status_code = 404


class ValidationError(APIError):
    """Validation failed."""
    status_code = 400


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for the app."""
    
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify({
            'success': False,
            'error': error.message,
        }), error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({
            'success': False,
            'error': 'Resource not found',
        }), 404
    
    @app.errorhandler(500)
    def handle_server_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
        }), 500
```

## Query Parameters

### ✅ GOOD - Consistent query param handling

```python
@articles_bp.route('/articles', methods=['GET'])
def list_articles():
    """List articles with filtering and pagination."""
    # Filtering
    sport = request.args.get('sport')
    author_id = request.args.get('author_id', type=int)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Sorting
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    
    # Build query
    query = Article.query
    
    if sport:
        query = query.filter(Article.sport == sport)
    if author_id:
        query = query.filter(Article.author_id == author_id)
    
    # Apply sorting
    if order == 'desc':
        query = query.order_by(getattr(Article, sort_by).desc())
    else:
        query = query.order_by(getattr(Article, sort_by).asc())
    
    # Apply pagination
    articles = query.paginate(page=page, per_page=per_page)
    
    return success_response({
        'items': [a.to_dict() for a in articles.items],
        'pagination': {
            'page': articles.page,
            'per_page': articles.per_page,
            'total': articles.total,
            'pages': articles.pages,
        }
    })
```

## Summary Checklist

- [ ] Use RESTful URL patterns
- [ ] Use Flask Blueprints for organization
- [ ] Return consistent JSON responses
- [ ] Use Pydantic for request validation
- [ ] Register centralized error handlers
- [ ] Handle query parameters consistently (filter, sort, paginate)
- [ ] Add proper HTTP status codes (200, 201, 400, 404, 500)