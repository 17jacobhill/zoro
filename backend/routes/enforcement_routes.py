from flask import Blueprint, request, jsonify
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

from backend.assistant.plan_manager import load_plan
from backend.assistant.services.enforcement_service import (
    get_enforcement_record,
    upsert_enforcement_record,
)
from backend.assistant.services.enforcement_v2_service import (
    get_enforcement_v2_record,
    add_requirements,
    add_user_requirement,
    update_verifications,
    update_tests,
    delete_requirement,
)
from backend.globals.schemas import (
    VerifyResult,
    TestResult,
    IndividualTestResult,
    Requirement,
    RequirementVerification,
    RequirementTest,
    FileSummary,
    CodeBlock,
    StepVerification,
    RuleAnalysis,
)

enforcement_bp = Blueprint('enforcement', __name__)
logger = logging.getLogger(__name__)

CLINE_API_BASE = "http://localhost:3000"

def handle_error(endpoint_name, error, status_code=500):
    logger.error(f"Error in {endpoint_name}: {str(error)}", exc_info=True)
    return jsonify({'success': False, 'error': str(error)}), status_code

@enforcement_bp.route('/api/enforcement/<chat_id>/<node_id>/<target_kind>/<target_id>', methods=['GET'])
def get_enforcement_record_api(chat_id, node_id, target_kind, target_id):
    try:
        logger.info(f"GET /api/enforcement/{chat_id}/{node_id}/{target_kind}/{target_id} - Started")
        
        record = get_enforcement_record(chat_id, node_id, target_kind, target_id)
        
        if not record:
            logger.info("GET enforcement record - Not Found")
            return jsonify({'success': True, 'record': None})
        
        logger.info("GET enforcement record - Success")
        return jsonify({'success': True, 'record': record.model_dump()})
    except Exception as e:
        return handle_error('get_enforcement_record', e)

@enforcement_bp.route('/api/enforcement/verify', methods=['POST'])
def enforcement_verify():
    try:
        logger.info("POST /api/enforcement/verify - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_kind = data.get('target_kind', '').strip()
        target_id = data.get('target_id', '').strip()
        
        if not all([chat_id, node_id, target_kind, target_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if target_kind != 'substep':
            logger.warning(f"Rejected verification for target_kind: {target_kind}")
            return jsonify({
                'success': False, 
                'error': f'Only substep verification is supported. Got: {target_kind}'
            }), 400
        
        plan = load_plan(chat_id)
        node = next((n for n in plan.nodes if n.id == node_id), None) if plan else None
        node_data = node.model_dump() if node else None
        
        cline_url = f"{CLINE_API_BASE}/verify-substep"
        payload = {
            'chat_id': chat_id,
            'step_id': node_id,
            'substep_id': target_id,
            'node': node_data
        }
        
        try:
            logger.info(f"Calling Cline API: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=300)
            response.raise_for_status()
            cline_data = response.json()
            logger.info(f"Cline API response: verdict={cline_data.get('verdict')}")
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            cline_data = {
                'verdict': 'unclear',
                'message': f'Cline API error: {str(e)}',
                'files_summary': [],
                'code_blocks': [],
                'tracking_commands': []
            }
        
        verdict = cline_data.get('verdict', 'unclear')
        overview = cline_data.get('overview', 'No overview provided')
        rules_analysis = cline_data.get('rules_analysis', [])
        files_summary = cline_data.get('files_summary', [])
        code_blocks = cline_data.get('code_blocks', [])
        
        verify_result = VerifyResult(
            verdict=verdict,
            overview=overview,
            rules_analysis=rules_analysis,
            files_summary=files_summary,
            code_blocks=code_blocks,
            timestamp=datetime.now().isoformat()
        )
        
        record = upsert_enforcement_record(
            chat_id=chat_id,
            node_id=node_id,
            target_kind=target_kind,
            target_id=target_id,
            verify=verify_result
        )
        
        logger.info("POST /api/enforcement/verify - Success")
        return jsonify({
            'success': True,
            'verdict': verdict,
            'overview': overview,
            'rules_analysis': rules_analysis,
            'files_summary': files_summary,
            'code_blocks': code_blocks,
            'record': record.model_dump()
        })
    except Exception as e:
        return handle_error('enforcement_verify', e)

@enforcement_bp.route('/api/enforcement/test', methods=['POST'])
def enforcement_test():
    try:
        logger.info("POST /api/enforcement/test - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_kind = data.get('target_kind', '').strip()
        target_id = data.get('target_id', '').strip()
        
        if not all([chat_id, node_id, target_kind, target_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if target_kind != 'substep':
            logger.warning(f"Rejected testing for target_kind: {target_kind}")
            return jsonify({
                'success': False, 
                'error': f'Only substep testing is supported. Got: {target_kind}'
            }), 400
        
        plan = load_plan(chat_id)
        node = next((n for n in plan.nodes if n.id == node_id), None) if plan else None
        node_data = node.model_dump() if node else None
        
        record = get_enforcement_record(chat_id, node_id, target_kind, target_id)
        cached_verification = None
        if record and record.verify:
            logger.info("Found cached verification - using it instead of re-running verification")
            cached_verification = {
                'verdict': record.verify.verdict,
                'overview': record.verify.overview,
                'rules_analysis': [r.model_dump() for r in record.verify.rules_analysis],
                'files_summary': [f.model_dump() for f in record.verify.files_summary],
                'code_blocks': [c.model_dump() for c in record.verify.code_blocks],
            }
        
        cline_url = f"{CLINE_API_BASE}/test-substep"
        payload = {
            'chat_id': chat_id,
            'step_id': node_id,
            'substep_id': target_id,
            'node': node_data,
            'cached_verification': cached_verification
        }
        
        test_file = ""
        test_results = []
        error_msg = None
        
        try:
            logger.info(f"Calling Cline API: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=900)
            response.raise_for_status()
            cline_data = response.json()
            
            test_file = cline_data.get('test_file', '')
            test_results = [
                IndividualTestResult(**test) 
                for test in cline_data.get('results', [])
            ]
            error_msg = cline_data.get('error')
            logger.info(f"Cline tests generated: {len(test_results)} tests")
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            error_msg = f"Cline API error: {str(e)}"
        
        test_result = TestResult(
            test_file=test_file,
            results=test_results,
            error=error_msg,
            timestamp=datetime.now().isoformat()
        )
        
        record = upsert_enforcement_record(
            chat_id=chat_id,
            node_id=node_id,
            target_kind=target_kind,
            target_id=target_id,
            test=test_result
        )
        
        logger.info("POST /api/enforcement/test - Success")
        return jsonify({
            'success': True,
            'test_file': test_file,
            'results': [r.model_dump() for r in test_results],
            'error': error_msg,
            'record': record.model_dump()
        })
    except Exception as e:
        return handle_error('enforcement_test', e)

@enforcement_bp.route('/api/enforcement/v2/<chat_id>/<node_id>/<target_id>', methods=['GET'])
def get_enforcement_v2_record_api(chat_id, node_id, target_id):
    try:
        logger.info(f"GET /api/enforcement/v2/{chat_id}/{node_id}/{target_id} - Started")
        
        record = get_enforcement_v2_record(chat_id, node_id, target_id)
        
        if not record:
            logger.info("GET enforcement v2 record - Not Found")
            return jsonify({'success': True, 'record': None})
        
        logger.info("GET enforcement v2 record - Success")
        return jsonify({'success': True, 'record': record.model_dump()})
    except Exception as e:
        return handle_error('get_enforcement_v2_record', e)

@enforcement_bp.route('/api/enforcement/v2/list-requirements', methods=['POST'])
def enforcement_v2_list_requirements():
    try:
        logger.info("POST /api/enforcement/v2/list-requirements - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_id = data.get('target_id', '').strip()
        
        if not all([chat_id, node_id, target_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        plan = load_plan(chat_id)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        node = next((n for n in plan.nodes if n.id == node_id), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404
        
        substep = next((s for s in (node.substeps or []) if isinstance(s, dict) and s.get('id') == target_id), None)
        if not substep:
            return jsonify({'success': False, 'error': 'Substep not found'}), 404
        
        step_description = node.description or "No description"
        substep_description = substep.get('text', 'No description')
        rules = [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'description': r.description
            }
            for r in (node.rules or [])
        ]
        
        cline_url = f"{CLINE_API_BASE}/generate-requirements"
        payload = {
            'chat_id': chat_id,
            'node_id': node_id,
            'target_id': target_id,
            'step_description': step_description,
            'substep_description': substep_description,
            'rules': rules
        }
        
        try:
            logger.info(f"Calling Cline: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=120)
            response.raise_for_status()
            cline_data = response.json()
            
            if not cline_data.get('success'):
                raise Exception(cline_data.get('error', 'Unknown Cline error'))
            
            raw_requirements = cline_data.get('requirements', [])
            record = add_requirements(chat_id, node_id, target_id, raw_requirements)
            
            logger.info(f"POST /api/enforcement/v2/list-requirements - Success ({len(record.requirements)} requirements)")
            return jsonify({
                'success': True,
                'requirements': [r.model_dump() for r in record.requirements]
            })
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            return jsonify({'success': False, 'error': f'Cline API error: {str(e)}'}), 500
    except Exception as e:
        return handle_error('enforcement_v2_list_requirements', e)

@enforcement_bp.route('/api/enforcement/v2/add-requirement', methods=['POST'])
def enforcement_v2_add_requirement():
    try:
        logger.info("POST /api/enforcement/v2/add-requirement - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_id = data.get('target_id', '').strip()
        description = data.get('description', '').strip()
        category = data.get('category', '').strip()
        
        if not all([chat_id, node_id, target_id, description, category]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if category not in ['feature', 'rule', 'integration', 'edge']:
            return jsonify({'success': False, 'error': 'Invalid category'}), 400
        
        record = add_user_requirement(
            chat_id=chat_id,
            node_id=node_id,
            target_id=target_id,
            description=description,
            category=category
        )
        
        new_requirement = record.requirements[-1]
        
        logger.info("POST /api/enforcement/v2/add-requirement - Success")
        return jsonify({
            'success': True,
            'requirement': new_requirement.model_dump()
        })
    except Exception as e:
        return handle_error('enforcement_v2_add_requirement', e)

@enforcement_bp.route('/api/enforcement/v2/delete-requirement', methods=['POST'])
def enforcement_v2_delete_requirement():
    try:
        logger.info("POST /api/enforcement/v2/delete-requirement - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_id = data.get('target_id', '').strip()
        requirement_id = data.get('requirement_id', '').strip()
        
        if not all([chat_id, node_id, target_id, requirement_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        success = delete_requirement(
            chat_id=chat_id,
            node_id=node_id,
            target_id=target_id,
            requirement_id=requirement_id
        )
        
        if success:
            logger.info("POST /api/enforcement/v2/delete-requirement - Success")
            return jsonify({'success': True, 'requirement_id': requirement_id})
        else:
            logger.info("POST /api/enforcement/v2/delete-requirement - Not Found")
            return jsonify({'success': False, 'error': 'Requirement not found'}), 404
    except Exception as e:
        return handle_error('enforcement_v2_delete_requirement', e)

@enforcement_bp.route('/api/enforcement/v2/verify', methods=['POST'])
def enforcement_v2_verify():
    try:
        logger.info("POST /api/enforcement/v2/verify - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_id = data.get('target_id', '').strip()
        requirements = data.get('requirements', [])
        
        if not all([chat_id, node_id, target_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not requirements:
            return jsonify({'success': False, 'error': 'No requirements provided'}), 400
        
        plan = load_plan(chat_id)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        node = next((n for n in plan.nodes if n.id == node_id), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404
        
        substep = next((s for s in (node.substeps or []) if isinstance(s, dict) and s.get('id') == target_id), None)
        if not substep:
            return jsonify({'success': False, 'error': 'Substep not found'}), 404
        
        step_description = node.description or "No description"
        substep_description = substep.get('text', 'No description')
        
        cline_url = f"{CLINE_API_BASE}/verify-substep-requirements"
        payload = {
            'chat_id': chat_id,
            'node_id': node_id,
            'target_id': target_id,
            'step_description': step_description,
            'substep_description': substep_description,
            'requirements': requirements
        }
        
        try:
            logger.info(f"Calling Cline: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=300)
            response.raise_for_status()
            cline_data = response.json()
            
            if not cline_data.get('success'):
                raise Exception(cline_data.get('error', 'Unknown Cline error'))
            
            raw_verifications = cline_data.get('verifications', [])
            
            verifications = [
                RequirementVerification(
                    requirement_id=v['requirement_id'],
                    verdict=v['verdict'],
                    evidence=v['evidence'],
                    files_changed=[FileSummary(**f) for f in v.get('files_changed', [])],
                    code_changed=[CodeBlock(**c) for c in v.get('code_changed', [])]
                )
                for v in raw_verifications
            ]
            
            all_pass = all(v.verdict == "pass" for v in verifications)
            any_pass = any(v.verdict == "pass" for v in verifications)
            
            if all_pass:
                overall_verdict = "done"
            elif any_pass:
                overall_verdict = "partial"
            else:
                overall_verdict = "not_done"
            
            record = update_verifications(
                chat_id, 
                node_id, 
                target_id, 
                verifications
            )
            
            logger.info(f"POST /api/enforcement/v2/verify - Success (verdict: {overall_verdict})")
            return jsonify({
                'success': True,
                'verifications': [v.model_dump() for v in verifications],
                'overall_verdict': overall_verdict
            })
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            return jsonify({'success': False, 'error': f'Cline API error: {str(e)}'}), 500
    except Exception as e:
        return handle_error('enforcement_v2_verify', e)

@enforcement_bp.route('/api/enforcement/v2/test', methods=['POST'])
def enforcement_v2_test():
    try:
        logger.info("POST /api/enforcement/v2/test - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        target_id = data.get('target_id', '').strip()
        requirements = data.get('requirements', [])
        
        if not all([chat_id, node_id, target_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not requirements:
            return jsonify({'success': False, 'error': 'No requirements provided'}), 400
        
        plan = load_plan(chat_id)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        node = next((n for n in plan.nodes if n.id == node_id), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404
        
        substep = next((s for s in (node.substeps or []) if isinstance(s, dict) and s.get('id') == target_id), None)
        if not substep:
            return jsonify({'success': False, 'error': 'Substep not found'}), 404
        
        step_description = node.description or "No description"
        substep_description = substep.get('text', 'No description')
        
        cline_url = f"{CLINE_API_BASE}/test-substep-requirements"
        payload = {
            'chat_id': chat_id,
            'node_id': node_id,
            'target_id': target_id,
            'step_description': step_description,
            'substep_description': substep_description,
            'requirements': requirements
        }
        
        try:
            logger.info(f"Calling Cline: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=600)
            response.raise_for_status()
            cline_data = response.json()
            
            if not cline_data.get('success'):
                raise Exception(cline_data.get('error', 'Unknown Cline error'))
            
            raw_tests = cline_data.get('tests', [])
            
            tests = [
                RequirementTest(
                    requirement_id=t['requirement_id'],
                    test_name=t['test_name'],
                    test_description=t['test_description'],
                    test_code=t['test_code'],
                    status=t['status'],
                    output=t.get('output', '')
                )
                for t in raw_tests
            ]
            
            record = update_tests(
                chat_id, 
                node_id, 
                target_id, 
                tests
            )
            
            logger.info(f"POST /api/enforcement/v2/test - Success ({len(tests)} tests)")
            return jsonify({
                'success': True,
                'tests': [t.model_dump() for t in tests]
            })
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            return jsonify({'success': False, 'error': f'Cline API error: {str(e)}'}), 500
    except Exception as e:
        return handle_error('enforcement_v2_test', e)

@enforcement_bp.route('/api/enforcement/v2/verify-step', methods=['POST'])
def enforcement_v2_verify_step():
    try:
        logger.info("POST /api/enforcement/v2/verify-step - Started")
        
        data = request.json or {}
        chat_id = data.get('chat_id', '').strip()
        node_id = data.get('node_id', '').strip()
        
        if not all([chat_id, node_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        plan = load_plan(chat_id)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        node = next((n for n in plan.nodes if n.id == node_id), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404
        
        cline_url = f"{CLINE_API_BASE}/verify-step"
        payload = {
            'chat_id': chat_id,
            'node_id': node_id,
            'node': node.model_dump()
        }
        
        try:
            logger.info(f"Calling Cline: {cline_url}")
            response = requests.post(cline_url, json=payload, timeout=300)
            response.raise_for_status()
            cline_data = response.json()
            
            if not cline_data.get('success'):
                raise Exception(cline_data.get('error', 'Unknown Cline error'))
            
            from backend.assistant.services.enforcement_v2_service import update_step_verification
            
            verification = StepVerification(
                verdict=cline_data['verdict'],
                overview=cline_data['overview'],
                rules_analysis=[RuleAnalysis(**r) for r in cline_data['rules_analysis']],
                files_summary=[FileSummary(**f) for f in cline_data.get('files_summary', [])],
                code_blocks=[CodeBlock(**c) for c in cline_data.get('code_blocks', [])],
                timestamp=datetime.now().isoformat()
            )
            
            record = update_step_verification(chat_id, node_id, verification)
            
            logger.info("POST /api/enforcement/v2/verify-step - Success")
            return jsonify({
                'success': True,
                'verification': verification.model_dump(),
                'node': node.model_dump()
            })
        except requests.RequestException as e:
            logger.error(f"Cline API error: {str(e)}")
            return jsonify({'success': False, 'error': f'Cline API error: {str(e)}'}), 500
    except Exception as e:
        return handle_error('enforcement_v2_verify_step', e)