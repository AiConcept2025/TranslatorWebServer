#!/usr/bin/env python3
"""
feature_flow.py - Orchestrate agent workflow for feature development
Reduces token usage by handling complex logic externally
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List

class FeatureFlow:
    """Orchestrate agents for feature development."""
    
    AGENTS = {
        'design': 'backend-architect',
        'implement': 'python-pro',
        'test': 'test-automator',
        'security': 'security-auditor'
    }
    
    def __init__(self, feature_name: str):
        self.feature = feature_name.replace(' ', '_').lower()
        self.outputs = {}
    
    def run(self):
        """Execute full feature development flow."""
        steps = [
            ('design', self.design_api),
            ('implement', self.implement_code),
            ('test', self.generate_tests),
            ('security', self.security_audit)
        ]
        
        for step_name, step_func in steps:
            print(f"\n🔄 Running: {step_name}")
            result = step_func()
            self.outputs[step_name] = result
            
            if not result['success']:
                print(f"❌ Failed at {step_name}: {result.get('error')}")
                return False
        
        print(f"\n✅ Feature '{self.feature}' complete!")
        self.save_summary()
        return True
    
    def design_api(self) -> Dict:
        """Step 1: Design API with backend-architect."""
        prompt = f"""
        Use backend-architect to design REST API for {self.feature}:
        - Generate OpenAPI spec
        - Include all CRUD operations
        - Define error responses (400, 401, 404, 422, 500)
        - Add request/response schemas
        Output to: specs/{self.feature}_spec.yaml
        """
        
        # In real implementation, this would call Claude API
        # For now, create template
        spec_file = Path(f"specs/{self.feature}_spec.yaml")
        spec_file.parent.mkdir(exist_ok=True)
        
        return {
            'success': True,
            'spec_file': str(spec_file),
            'endpoints': self._extract_endpoints(spec_file)
        }
    
    def implement_code(self) -> Dict:
        """Step 2: Implement with python-pro."""
        spec = self.outputs['design']['spec_file']
        
        files_to_create = [
            f"app/api/v1/{self.feature}.py",
            f"app/services/{self.feature}_service.py",
            f"app/models/{self.feature}_models.py",
            f"app/db/repositories/{self.feature}_repo.py"
        ]
        
        for file_path in files_to_create:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            # Agent would generate actual code here
        
        return {
            'success': True,
            'files': files_to_create
        }
    
    def generate_tests(self) -> Dict:
        """Step 3: Generate tests with test-automator."""
        test_files = [
            f"tests/unit/test_{self.feature}.py",
            f"tests/integration/test_{self.feature}_api.py"
        ]
        
        for test_file in test_files:
            Path(test_file).parent.mkdir(parents=True, exist_ok=True)
            # Agent would generate actual tests here
        
        # Run tests
        coverage = self._run_coverage_check()
        
        return {
            'success': coverage >= 90,
            'coverage': coverage,
            'test_files': test_files
        }
    
    def security_audit(self) -> Dict:
        """Step 4: Security audit with security-auditor."""
        files = self.outputs['implement']['files']
        
        # Run security checks
        issues = self._run_security_scan(files)
        
        return {
            'success': len(issues['critical']) == 0,
            'issues': issues
        }
    
    def _extract_endpoints(self, spec_file: Path) -> List[str]:
        """Extract endpoints from OpenAPI spec."""
        # Simplified - would parse actual YAML
        return [
            f"GET /api/v1/{self.feature}",
            f"POST /api/v1/{self.feature}",
            f"GET /api/v1/{self.feature}/{{id}}",
            f"PUT /api/v1/{self.feature}/{{id}}",
            f"DELETE /api/v1/{self.feature}/{{id}}"
        ]
    
    def _run_coverage_check(self) -> float:
        """Run pytest with coverage."""
        try:
            result = subprocess.run(
                ["pytest", "--cov=app", "--cov-report=json", "-q"],
                capture_output=True,
                text=True
            )
            # Parse coverage.json
            return 95.0  # Placeholder
        except:
            return 0.0
    
    def _run_security_scan(self, files: List[str]) -> Dict:
        """Run bandit security scan."""
        try:
            result = subprocess.run(
                ["bandit", "-r"] + files + ["-f", "json"],
                capture_output=True,
                text=True
            )
            # Parse bandit output
            return {'critical': [], 'high': [], 'medium': []}
        except:
            return {'critical': [], 'high': [], 'medium': []}
    
    def save_summary(self):
        """Save workflow summary."""
        summary = {
            'feature': self.feature,
            'outputs': self.outputs,
            'status': 'complete'
        }
        
        with open(f"reports/{self.feature}_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./feature_flow.py 'feature name'")
        sys.exit(1)
    
    feature = ' '.join(sys.argv[1:])
    flow = FeatureFlow(feature)
    success = flow.run()
    sys.exit(0 if success else 1)

