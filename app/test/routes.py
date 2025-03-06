from flask import render_template, current_app, jsonify, request
from . import test_bp
import traceback
import jinja2
import os

@test_bp.route('/')
def index():
    """Test homepage - lists all available tests"""
    tests = [
        {'name': 'Basic Template', 'route': '/test/basic', 'description': 'Tests basic template rendering'},
        {'name': 'Template Inheritance', 'route': '/test/inheritance', 'description': 'Tests template inheritance and blocks'},
        {'name': 'Template Variables', 'route': '/test/variables', 'description': 'Tests variable passing and rendering'},
        {'name': 'Template Conditionals', 'route': '/test/conditionals', 'description': 'Tests conditional logic in templates'},
        {'name': 'Template Loops', 'route': '/test/loops', 'description': 'Tests loops in templates'},
        {'name': 'Template Filters', 'route': '/test/filters', 'description': 'Tests built-in filters'},
        {'name': 'Template Macros', 'route': '/test/macros', 'description': 'Tests template macros'},
        {'name': 'Error Handling', 'route': '/test/error', 'description': 'Tests error handling in templates'},
        {'name': 'Template Directory Listing', 'route': '/test/list-templates', 'description': 'Lists all available templates'},
    ]
    
    return render_template('test/index.html', tests=tests)

@test_bp.route('/basic')
def basic_template():
    """Test basic template rendering"""
    try:
        return render_template('test/basic.html')
    except Exception as e:
        return render_error('test/basic.html', e)

@test_bp.route('/inheritance')
def template_inheritance():
    """Test template inheritance"""
    try:
        return render_template('test/inheritance.html', 
                              title='Inheritance Test', 
                              content='This tests template inheritance')
    except Exception as e:
        return render_error('test/inheritance.html', e)

@test_bp.route('/variables')
def template_variables():
    """Test template variables"""
    try:
        test_vars = {
            'string_var': 'This is a string',
            'int_var': 42,
            'float_var': 3.14159,
            'bool_var': True,
            'list_var': ['item1', 'item2', 'item3'],
            'dict_var': {'key1': 'value1', 'key2': 'value2'},
            'none_var': None
        }
        
        return render_template('test/variables.html', **test_vars)
    except Exception as e:
        return render_error('test/variables.html', e)

@test_bp.route('/conditionals')
def template_conditionals():
    """Test template conditionals"""
    try:
        conditions = {
            'condition_true': True,
            'condition_false': False,
            'value_empty': '',
            'value_zero': 0,
            'value_none': None,
            'value_string': 'Test string',
            'value_list': [1, 2, 3],
        }
        
        return render_template('test/conditionals.html', **conditions)
    except Exception as e:
        return render_error('test/conditionals.html', e)

@test_bp.route('/loops')
def template_loops():
    """Test template loops"""
    try:
        loop_data = {
            'empty_list': [],
            'numbers': list(range(1, 11)),
            'fruits': ['apple', 'banana', 'orange', 'grape', 'kiwi'],
            'users': [
                {'name': 'Alice', 'age': 25, 'active': True},
                {'name': 'Bob', 'age': 30, 'active': False},
                {'name': 'Charlie', 'age': 35, 'active': True},
                {'name': 'David', 'age': 40, 'active': True},
            ],
            'nested_list': [
                [1, 2, 3],
                [4, 5, 6],
                [7, 8, 9]
            ]
        }
        
        return render_template('test/loops.html', **loop_data)
    except Exception as e:
        return render_error('test/loops.html', e)

@test_bp.route('/filters')
def template_filters():
    """Test template filters"""
    try:
        filter_data = {
            'lowercase_string': 'THIS SHOULD BE LOWERCASE',
            'uppercase_string': 'this should be uppercase',
            'capitalize_string': 'this should be capitalized',
            'number': 12345.6789,
            'list_to_join': ['apple', 'banana', 'orange'],
            'html_string': '<script>alert("XSS attack!");</script>',
            'long_text': 'This is a long text that should be truncated at some point',
            'date_value': '2025-03-03',
        }
        
        return render_template('test/filters.html', **filter_data)
    except Exception as e:
        return render_error('test/filters.html', e)

@test_bp.route('/macros')
def template_macros():
    """Test template macros"""
    try:
        macro_data = {
            'form_fields': [
                {'type': 'text', 'name': 'username', 'label': 'Username', 'required': True},
                {'type': 'email', 'name': 'email', 'label': 'Email Address', 'required': True},
                {'type': 'password', 'name': 'password', 'label': 'Password', 'required': True},
                {'type': 'checkbox', 'name': 'remember', 'label': 'Remember Me', 'required': False},
            ],
            'buttons': [
                {'type': 'primary', 'text': 'Submit'},
                {'type': 'secondary', 'text': 'Cancel'},
                {'type': 'danger', 'text': 'Delete'},
            ]
        }
        
        return render_template('test/macros.html', **macro_data)
    except Exception as e:
        return render_error('test/macros.html', e)

@test_bp.route('/error')
def template_error():
    """Test template error handling"""
    error_type = request.args.get('type', 'undefined_variable')
    
    try:
        if error_type == 'undefined_variable':
            # Intentionally use an undefined variable
            return render_template('test/error_undefined_var.html')
        elif error_type == 'syntax_error':
            # Template with syntax error
            return render_template('test/error_syntax.html')
        elif error_type == 'missing_template':
            # Non-existent template
            return render_template('test/non_existent_template.html')
        else:
            return "Unknown error type"
    except Exception as e:
        return render_error(f'test/error_{error_type}.html', e)

@test_bp.route('/list-templates')
def list_templates():
    """List all templates in the application"""
    template_dir = os.path.join(current_app.root_path, 'templates')
    templates = []
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                rel_path = os.path.relpath(os.path.join(root, file), template_dir)
                templates.append(rel_path)
    
    return render_template('test/list_templates.html', templates=sorted(templates))

def render_error(template_name, error):
    """Render template error details"""
    error_details = {
        'template': template_name,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }
    
    return render_template('test/error_details.html', **error_details)

@test_bp.route('/check-template-file')
def check_template_file():
    """Check if a template file exists and return its contents"""
    template_name = request.args.get('template', '')
    if not template_name:
        return jsonify({'error': 'No template specified'})
    
    template_path = os.path.join(current_app.root_path, 'templates', template_name)
    
    if not os.path.exists(template_path):
        return jsonify({
            'exists': False,
            'template': template_name,
            'error': 'Template file does not exist'
        })
    
    try:
        with open(template_path, 'r') as f:
            content = f.read()
        
        return jsonify({
            'exists': True,
            'template': template_name,
            'content': content
        })
    except Exception as e:
        return jsonify({
            'exists': True,
            'template': template_name,
            'error': str(e)
        }) 