# Test package initialization
from flask import Blueprint

test_bp = Blueprint('test', __name__)

from . import routes 