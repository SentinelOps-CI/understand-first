#!/bin/bash

# Understand-First Installation Script
# This script provides a one-command installation experience

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
            print_success "Python $PYTHON_VERSION found"
            return 0
        else
            print_error "Python 3.9+ required, found $PYTHON_VERSION"
            return 1
        fi
    else
        print_error "Python 3 not found"
        return 1
    fi
}

# Function to install from PyPI
install_from_pypi() {
    print_status "Installing from PyPI..."
    pip install understand-first
    print_success "Understand-First installed successfully!"
}

# Function to install from source
install_from_source() {
    print_status "Installing from source..."
    
    # Clone repository if not already present
    if [ ! -d "understand-first" ]; then
        print_status "Cloning repository..."
        git clone https://github.com/sentinelops-ci/understand-first.git
    fi
    
    cd understand-first
    
    # Install in development mode
    print_status "Installing in development mode..."
    if command -v uv >/dev/null 2>&1; then
        uv sync --all-extras
    else
        pip install -e ".[dev,examples]"
    fi
    
    print_success "Understand-First installed from source!"
}

# Function to run post-installation checks
post_install_check() {
    print_status "Running post-installation checks..."
    
    if command_exists u; then
        print_success "CLI tool 'u' is available"
        u --help > /dev/null 2>&1 && print_success "CLI is working correctly"
    else
        print_warning "CLI tool 'u' not found in PATH"
    fi
    
    # Run doctor command
    if command_exists u; then
        print_status "Running system health check..."
        u doctor
    fi
}

# Function to show usage
show_usage() {
    echo "Understand-First Installation Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --pypi     Install from PyPI (default)"
    echo "  --source   Install from source"
    echo "  --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Install from PyPI"
    echo "  $0 --pypi            # Install from PyPI"
    echo "  $0 --source          # Install from source"
}

# Main installation function
main() {
    local install_method="pypi"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --pypi)
                install_method="pypi"
                shift
                ;;
            --source)
                install_method="source"
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    print_status "Starting Understand-First installation..."
    
    # Check Python
    if ! check_python; then
        print_error "Please install Python 3.9+ and try again"
        exit 1
    fi
    
    # Check pip
    if ! command_exists pip; then
        print_error "pip not found. Please install pip and try again"
        exit 1
    fi
    
    # Install based on method
    case $install_method in
        pypi)
            install_from_pypi
            ;;
        source)
            install_from_source
            ;;
    esac
    
    # Post-installation checks
    post_install_check
    
    print_success "Installation completed!"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'u --help' to see available commands"
    echo "  2. Run 'u demo' to see a complete example"
    echo "  3. Run 'u doctor' to check system health"
    echo "  4. Visit https://github.com/sentinelops-ci/understand-first for documentation"
}

# Run main function
main "$@"
