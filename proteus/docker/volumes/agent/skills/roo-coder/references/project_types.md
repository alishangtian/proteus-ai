# Project Type Detection & Patterns

## 🎯 **IMPORTANT: Project Location Convention**

**All Roo-Coder projects MUST be located within `/app/data/{project_name}` directory:**

### Why Use `/app/data/{project_name}`?
1. **File Persistence**: Files saved here persist across sessions
2. **Consistent Paths**: Uniform project structure for all operations
3. **Network Accessibility**: Files accessible via `http://host:port/app/data/{file_name}`
4. **Skill Compatibility**: Ensures compatibility with other Proteus skills and tools
5. **Backup & Recovery**: Proper location for automatic backups

### Example Project Paths:
```
/app/data/my-web-app/          # Web application project
/app/data/api-service/         # Backend API service  
/app/data/data-analysis/       # Data science project
/app/data/mobile-app/         # Mobile application
/app/data/automation-scripts/ # Automation scripts
```

### Project Setup Commands:
```bash
# Create project directory
mkdir -p /app/data/my-project

# Navigate to project
cd /app/data/my-project

# Initialize project structure
python /app/.proteus/skills/roo-coder/scripts/config_check.py --create-structure
```

---

## Common Project Types


## Common Project Types

### Python Projects
**Indicators**:
- `requirements.txt`, `setup.py`, `pyproject.toml`, `Pipfile`, `Pipfile.lock`
- `*.py` files, `__init__.py` files
- `venv/`, `.venv/`, `env/` directories

**Common Structures**:
```
python-project/
├── src/                    # Source code
│   ├── __init__.py
│   └── module/
│       └── __init__.py
├── tests/                  # Test files
│   ├── __init__.py
│   └── test_module.py
├── docs/                   # Documentation
├── requirements.txt        # Dependencies
├── setup.py               # Package setup
├── README.md
└── .gitignore
```

**Framework Detection**:
- **Django**: `manage.py`, `settings.py`, `urls.py`, `wsgi.py`
- **Flask**: `app.py`, `application.py`, `requirements.txt` with flask
- **FastAPI**: `main.py` with FastAPI imports, `requirements.txt` with fastapi
- **Pandas/NumPy**: Data analysis projects with data/ directory

### Node.js/JavaScript Projects
**Indicators**:
- `package.json`, `package-lock.json`, `yarn.lock`
- `node_modules/` directory
- `*.js`, `*.jsx`, `*.ts`, `*.tsx` files

**Common Structures**:
```
node-project/
├── src/                    # Source code
│   ├── index.js
│   └── components/
├── public/                 # Static assets
├── package.json           # Dependencies & scripts
├── package-lock.json
├── README.md
└── .gitignore
```

**Framework Detection**:
- **React**: `react`, `react-dom` in package.json, JSX files
- **Vue**: `vue` in package.json, `.vue` files
- **Angular**: `@angular/core` in package.json, TypeScript heavy
- **Express**: `express` in package.json, `app.js` or `server.js`
- **Next.js**: `next` in package.json, `pages/` directory
- **NestJS**: `@nestjs/core` in package.json, TypeScript decorators

### Java Projects
**Indicators**:
- `pom.xml` (Maven), `build.gradle`, `build.gradle.kts` (Gradle)
- `*.java` files
- `src/main/java/`, `src/test/java/` directories

**Common Structures**:
```
java-project/
├── src/
│   ├── main/
│   │   ├── java/          # Java source
│   │   └── resources/     # Config files
│   └── test/
│       ├── java/          # Test source
│       └── resources/     # Test resources
├── pom.xml               # Maven config
├── target/               # Build output (Maven)
└── .gitignore
```

### Go Projects
**Indicators**:
- `go.mod`, `go.sum`
- `*.go` files
- `vendor/` directory (optional)

**Common Structures**:
```
go-project/
├── cmd/                   # Command applications
│   └── app/
│       └── main.go
├── internal/             # Private application code
├── pkg/                  # Public library code
├── go.mod               # Module definition
├── go.sum               # Dependency checksums
└── .gitignore
```

### Rust Projects
**Indicators**:
- `Cargo.toml`, `Cargo.lock`
- `*.rs` files
- `src/` directory with `main.rs` or `lib.rs`

**Common Structures**:
```
rust-project/
├── src/
│   ├── main.rs          # Binary entry point
│   └── lib.rs           # Library entry point
├── Cargo.toml          # Package manifest
├── Cargo.lock          # Dependency lock
└── .gitignore
```

### Web Projects (HTML/CSS/JS)
**Indicators**:
- `index.html`, `*.html` files
- `*.css`, `*.scss`, `*.less` files
- `*.js` files without package.json (vanilla JS)

**Common Structures**:
```
web-project/
├── index.html           # Main HTML file
├── css/                 # Stylesheets
│   └── style.css
├── js/                  # JavaScript
│   └── main.js
├── images/              # Image assets
└── .gitignore
```

## Detection Algorithm

### Step 1: File System Scan
```python
def scan_for_indicators(directory):
    import os
    indicators = {}
    
    for root, dirs, files in os.walk(directory):
        # Check for key files
        for file in files:
            if file == 'package.json':
                indicators['node'] = True
            elif file == 'requirements.txt':
                indicators['python'] = True
            elif file == 'pom.xml':
                indicators['java'] = True
            elif file == 'go.mod':
                indicators['go'] = True
            elif file == 'Cargo.toml':
                indicators['rust'] = True
            elif file == 'Gemfile':
                indicators['ruby'] = True
            elif file == 'composer.json':
                indicators['php'] = True
            elif file.endswith('.html'):
                indicators['web'] = True
        
        # Check for directories
        if 'node_modules' in dirs:
            indicators['node'] = True
        if 'venv' in dirs or '.venv' in dirs:
            indicators['python'] = True
        if 'vendor' in dirs:
            if 'composer.json' in files:
                indicators['php'] = True
    
    return indicators
```

### Step 2: Framework Detection
```python
def detect_framework(directory, project_type):
    import os
    import json
    
    if project_type == 'node':
        # Check package.json for frameworks
        package_path = os.path.join(directory, 'package.json')
        if os.path.exists(package_path):
            with open(package_path, 'r') as f:
                package = json.load(f)
            
            deps = package.get('dependencies', {})
            dev_deps = package.get('devDependencies', {})
            all_deps = {**deps, **dev_deps}
            
            if 'react' in all_deps:
                return 'react'
            elif 'vue' in all_deps:
                return 'vue'
            elif '@angular/core' in all_deps:
                return 'angular'
            elif 'next' in all_deps:
                return 'nextjs'
            elif 'express' in all_deps:
                return 'express'
            elif '@nestjs/core' in all_deps:
                return 'nestjs'
    
    elif project_type == 'python':
        # Check requirements.txt or setup.py
        req_path = os.path.join(directory, 'requirements.txt')
        if os.path.exists(req_path):
            with open(req_path, 'r') as f:
                content = f.read().lower()
            
            if 'django' in content:
                return 'django'
            elif 'flask' in content:
                return 'flask'
            elif 'fastapi' in content:
                return 'fastapi'
    
    return 'standard'
```

## Project-Specific Conventions

### Python Conventions
- **Imports**: Standard library → third-party → local
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Documentation**: Docstrings (Google/NumPy style)
- **Testing**: pytest preferred, unittest acceptable

### JavaScript/TypeScript Conventions
- **Imports**: External → internal, alphabetical within groups
- **Naming**: camelCase for functions/variables, PascalCase for classes/components
- **Documentation**: JSDoc comments
- **Testing**: Jest, Mocha/Chai, or Vitest

### Java Conventions
- **Packages**: Reverse domain notation (com.example.project)
- **Naming**: camelCase for methods/variables, PascalCase for classes
- **Documentation**: Javadoc comments
- **Testing**: JUnit, TestNG

## Build & Dependency Management

### Build Tools by Language
- **Python**: pip, pipenv, poetry, setuptools
- **JavaScript**: npm, yarn, pnpm, bun
- **Java**: Maven, Gradle
- **Go**: go build, go mod
- **Rust**: cargo
- **Ruby**: bundler (gem)
- **PHP**: composer

### Dependency File Patterns
```python
DEPENDENCY_FILES = {
    'python': ['requirements.txt', 'Pipfile', 'pyproject.toml', 'setup.py'],
    'node': ['package.json', 'package-lock.json', 'yarn.lock'],
    'java': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    'go': ['go.mod', 'go.sum'],
    'rust': ['Cargo.toml', 'Cargo.lock'],
    'ruby': ['Gemfile', 'Gemfile.lock'],
    'php': ['composer.json', 'composer.lock']
}
```

## Tool Configuration Detection

### Linters & Formatters
```python
LINTER_CONFIGS = {
    'python': ['.flake8', 'pylintrc', 'pyproject.toml', 'setup.cfg'],
    'javascript': ['.eslintrc', '.eslintrc.js', '.eslintrc.json', '.prettierrc'],
    'typescript': ['tsconfig.json', 'tslint.json'],
    'java': ['checkstyle.xml', 'pmd.xml'],
    'go': ['.golangci.yml']
}
```

### CI/CD Configuration
```python
CI_CONFIGS = [
    '.github/workflows/',  # GitHub Actions
    '.gitlab-ci.yml',      # GitLab CI
    '.travis.yml',         # Travis CI
    'Jenkinsfile',         # Jenkins
    'azure-pipelines.yml', # Azure Pipelines
    'circleci/config.yml'  # CircleCI
]
```

## Project Health Indicators

### Good Indicators
1. **Clear structure**: Well-organized directories
2. **Documentation**: README, CONTRIBUTING, CODE_OF_CONDUCT
3. **Tests**: Test directory with comprehensive coverage
4. **CI/CD**: Automated testing and deployment
5. **Linting**: Code quality tools configured
6. **Dependency management**: Lock files present

### Warning Signs
1. **Large files**: Files > 1MB in source control
2. **Hardcoded secrets**: API keys, passwords in code
3. **No tests**: Missing test directory or files
4. **Outdated dependencies**: Old versions without updates
5. **Poor structure**: Files scattered randomly
6. **No .gitignore**: Unnecessary files tracked

## Migration & Upgrade Patterns

### Version Upgrades
1. **Check current versions**: `npm list`, `pip freeze`, `mvn dependency:tree`
2. **Review changelogs**: Breaking changes, new features
3. **Test incrementally**: Update one dependency at a time
4. **Update lock files**: `package-lock.json`, `requirements.txt`
5. **Run tests**: Ensure compatibility

### Framework Migration
1. **Analyze current codebase**: Size, complexity, dependencies
2. **Create migration plan**: Phased approach
3. **Setup parallel environment**: Both old and new running
4. **Migrate incrementally**: Feature by feature
5. **Test thoroughly**: Regression, performance, integration

## Best Practices by Project Type

### Python Best Practices
1. Use virtual environments
2. Follow PEP 8 style guide
3. Add type hints (Python 3.5+)
4. Write comprehensive tests
5. Use dependency pinning

### JavaScript/TypeScript Best Practices
1. Use strict mode
2. Add TypeScript for large projects
3. Follow ESLint rules
4. Write unit and integration tests
5. Bundle for production

### Java Best Practices
1. Follow Java naming conventions
2. Use dependency injection
3. Write comprehensive tests
4. Use logging instead of System.out
5. Handle exceptions properly

### Go Best Practices
1. Use gofmt for formatting
2. Write table-driven tests
3. Handle errors explicitly
4. Use interfaces appropriately
5. Keep packages focused
