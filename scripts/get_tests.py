#!/usr/bin/env python3
"""
gen_tests.py - Generate integration tests from OpenAPI spec
Reduces tokens by automating repetitive test generation
"""

import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List

TEST_TEMPLATE = '''import pytest
from httpx import AsyncClient
from fastapi import status

@pytest.mark.asyncio
class Test{resource}API:
    """Auto-generated integration tests for {resource}."""
    
{test_methods}
'''

METHOD_TEMPLATE = '''    async def test_{method}_{path_safe}(self, client: AsyncClient, auth_headers: dict):
        """Test {method_upper} {path}."""
        response = await client.{method}(
            "{path}",
            headers=auth_headers{body}
        )
        assert response.status_code == status.HTTP_{status_code}
        {validations}
'''

class TestGenerator:
    """Generate tests from OpenAPI specification."""
    
    def __init__(self, spec_path: str, output_dir: str = "tests/integration"):
        self.spec_path = Path(spec_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.spec = self._load_spec()
    
    def _load_spec(self) -> Dict:
        """Load OpenAPI specification."""
        if not self.spec_path.exists():
            # Create minimal spec if not exists
            return {
                'paths': {
                    '/api/v1/translations': {
                        'get': {'responses': {'200': {}}},
                        'post': {'responses': {'201': {}}}
                    }
                }
            }
        
        with open(self.spec_path) as f:
            if self.spec_path.suffix == '.yaml':
                return yaml.safe_load(f)
            else:
                return json.load(f)
    
    def generate(self):
        """Generate test files for all paths."""
        paths_by_resource = self._group_by_resource()
        
        for resource, paths in paths_by_resource.items():
            self._generate_resource_tests(resource, paths)
        
        print(f"✅ Generated {len(paths_by_resource)} test files")
    
    def _group_by_resource(self) -> Dict[str, Dict]:
        """Group paths by resource name."""
        resources = {}
        
        for path, methods in self.spec.get('paths', {}).items():
            # Extract resource name from path
            parts = path.split('/')
            resource = parts[3] if len(parts) > 3 else 'root'
            
            if resource not in resources:
                resources[resource] = {}
            resources[resource][path] = methods
        
        return resources
    
    def _generate_resource_tests(self, resource: str, paths: Dict):
        """Generate test file for a resource."""
        test_methods = []
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    test_method = self._generate_test_method(
                        method, path, details
                    )
                    test_methods.append(test_method)
        
        # Write test file
        test_content = TEST_TEMPLATE.format(
            resource=resource.title().replace('_', ''),
            test_methods='\n'.join(test_methods)
        )
        
        output_file = self.output_dir / f"test_{resource}_api.py"
        output_file.write_text(test_content)
        print(f"  📝 {output_file}")
    
    def _generate_test_method(self, method: str, path: str, details: Dict) -> str:
        """Generate a single test method."""
        path_safe = path.replace('/', '_').replace('{', '').replace('}', '')
        status_code = self._get_success_status(method)
        
        # Add request body for POST/PUT
        body = ''
        if method in ['post', 'put', 'patch']:
            body = ',\n            json={"test": "data"}'
        
        # Add response validations
        validations = self._generate_validations(details)
        
        return METHOD_TEMPLATE.format(
            method=method,
            method_upper=method.upper(),
            path=path,
            path_safe=path_safe,
            status_code=status_code,
            body=body,
            validations=validations
        )
    
    def _get_success_status(self, method: str) -> str:
        """Get expected success status code."""
        status_map = {
            'get': '200_OK',
            'post': '201_CREATED',
            'put': '200_OK',
            'patch': '200_OK',
            'delete': '204_NO_CONTENT'
        }
        return status_map.get(method, '200_OK')
    
    def _generate_validations(self, details: Dict) -> str:
        """Generate response validations."""
        validations = []
        
        # Check for response schema
        response_200 = details.get('responses', {}).get('200', {})
        content = response_200.get('content', {}).get('application/json', {})
        schema = content.get('schema', {})
        
        if schema.get('required'):
            for field in schema['required']:
                validations.append(f'assert "{field}" in response.json()')
        
        if not validations:
            validations.append('# Add specific validations here')
        
        return '\n        '.join(validations)

class PerformanceTestGenerator:
    """Generate performance tests."""
    
    @staticmethod
    def generate_perf_test(endpoint: str, output_file: str):
        """Generate performance test for endpoint."""
        
        test_content = f'''import pytest
import time
import statistics
from httpx import AsyncClient

@pytest.mark.performance
async def test_{endpoint.replace('/', '_')}_performance(client: AsyncClient):
    """Test {endpoint} meets performance SLA."""
    times = []
    
    for _ in range(10):
        start = time.perf_counter()
        response = await client.get("{endpoint}")
        times.append(time.perf_counter() - start)
        assert response.status_code == 200
    
    p95 = statistics.quantiles(times, n=20)[18]
    assert p95 < 0.2, f"P95 {{p95:.3f}}s exceeds 200ms SLA"
    print(f"✅ {endpoint} P95: {{p95*1000:.0f}}ms")
'''
        
        Path(output_file).write_text(test_content)
        print(f"  📊 Generated performance test: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./gen_tests.py <openapi_spec.yaml> [output_dir]")
        sys.exit(1)
    
    spec_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "tests/integration/generated"
    
    # Generate integration tests
    generator = TestGenerator(spec_path, output_dir)
    generator.generate()
    
    # Generate performance tests for critical endpoints
    perf_gen = PerformanceTestGenerator()
    critical_endpoints = [
        '/api/v1/translations',
        '/api/v1/health'
    ]
    
    for endpoint in critical_endpoints:
        perf_gen.generate_perf_test(
            endpoint,
            f"tests/performance/test_{endpoint.replace('/', '_')}_perf.py"
        )


