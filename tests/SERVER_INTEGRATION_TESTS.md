# Server Integration Tests Inventory

**Total Tests: 305+**
**Location:** `server/tests/integration/`
**Run Command:** `cd server && source venv/bin/activate && pytest tests/integration/ -v -s`

## Test Logging

All tests use the `TestLogger` utility for human-readable output:
- **PURPOSE** statement at test start
- **REQUEST** details with HTTP method, URL, body, headers
- **RESPONSE** with status code and body
- **CHECK** results showing PASS/FAIL
- **X-Test headers** sent with each request for server log traceability

---

## Test Files Overview

| File | Tests | Description |
|------|-------|-------------|
| test_api_basic.py | 2 | Basic CRUD operations via HTTP API |
| test_api_contract_translation_transactions.py | 8 | Translation transactions API contract |
| test_batch_webhook_transactions.py | 4 | Batch file webhook transactions |
| test_companies_edit.py | 15 | Company CRUD operations |
| test_company_users_edit.py | 14 | Company user management |
| test_confirm_endpoints_split.py | 16 | Enterprise/Individual confirm endpoints |
| test_confirm_square_payment.py | 8 | Square payment confirmation |
| test_dashboard.py | 7 | Dashboard metrics API |
| test_enterprise_transaction_metadata.py | ~10 | Enterprise transaction metadata |
| test_field_updates.py | 28 | Subscription/User/Company field updates |
| test_individual_user_translation_mode_metadata.py | 10 | Individual translation mode storage |
| test_nested_translation_flow.py | 5 | Nested document structure flow |
| test_orders_api.py | 18 | Orders API with authentication |
| test_pricing_api.py | 24 | Pricing calculation endpoints |
| test_submit_api.py | 10 | Submit endpoint validation |
| test_submit_with_database.py | 14 | Submit with database integration |
| test_subscriptions_create.py | 5 | Subscription creation validation |
| test_subscriptions_edit.py | 11 | Subscription update operations |
| test_table_updates.py | 4 | Table update operations |
| test_table_updates_simplified.py | 4 | Simplified table updates |
| test_transaction_confirm_nested.py | 5 | Nested transaction confirmation |
| test_transaction_confirm_square.py | 27 | Square transaction confirmation flow |
| test_transaction_decline_nested.py | 5 | Nested transaction decline |
| test_translation_mode.py | 18 | Translation mode enum/model tests |
| test_user_transaction_creation.py | 7 | User transaction ID generation |
| test_user_transaction_metadata.py | 14 | User transaction metadata handling |
| test_user_transaction_structure.py | 3 | User transaction structure validation |
| test_user_transactions_multi_document.py | 17 | Multi-document transaction handling |

---

## Detailed Test List by File

### test_api_basic.py (2 tests)
| Test | Purpose |
|------|---------|
| `TestCompanyAPI::test_get_companies` | GET /api/v1/companies returns companies list |
| `TestCompanyUserAPI::test_create_company_user` | POST /api/company-users creates a user |

### test_api_contract_translation_transactions.py (8 tests)
| Test | Purpose |
|------|---------|
| `test_transaction_list_response_structure` | Verify list response format |
| `test_transaction_object_field_types` | Verify field types in response |
| `test_pagination_parameters` | Test pagination support |
| `test_status_filter` | Test status filtering |
| `test_error_response_structure_400` | Verify 400 error format |
| `test_error_response_structure_404` | Verify 404 error format |
| `test_empty_result_set` | Handle empty results |
| `test_multiple_documents_in_api_response` | Multiple docs in response |

### test_batch_webhook_transactions.py (4 tests)
| Test | Purpose |
|------|---------|
| `test_batch_transaction_multiple_files` | Handle multiple files in batch |
| `test_all_files_same_transaction_id` | All files share transaction ID |
| `test_multiple_webhooks_same_transaction_id` | Multiple webhooks same transaction |
| `test_batch_prevents_index_errors` | Prevent index out of range errors |

### test_companies_edit.py (15 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestGetCompanies | test_get_all_companies_success | GET companies returns 200 |
| TestGetCompanies | test_get_all_companies_structure | Response structure validation |
| TestGetCompanies | test_get_all_companies_matches_database | Data matches DB |
| TestGetCompanies | test_get_companies_test_company_present | Test company in list |
| TestCreateCompany | test_create_company_success | Create company with all fields |
| TestCreateCompany | test_create_company_minimal | Create with minimal fields |
| TestCreateCompany | test_create_company_duplicate_name | Reject duplicate names |
| TestCreateCompany | test_create_company_invalid_data | Reject invalid data |
| TestUpdateCompany | test_update_company_description | Update description |
| TestUpdateCompany | test_update_company_contact_info | Update contact info |
| TestUpdateCompany | test_update_company_address | Update address |
| TestUpdateCompany | test_update_nonexistent_company | Handle missing company |
| TestDeleteCompany | test_delete_company_success | Delete company |
| TestDeleteCompany | test_delete_company_with_users | Delete company with users |
| TestDeleteCompany | test_delete_nonexistent_company | Handle missing company |

### test_company_users_edit.py (14 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestCreateCompanyUser | test_create_user_success | Create user successfully |
| TestCreateCompanyUser | test_create_user_minimal_fields | Create with minimal fields |
| TestCreateCompanyUser | test_create_user_duplicate_email | Reject duplicate email |
| TestCreateCompanyUser | test_create_user_invalid_email | Reject invalid email |
| TestCreateCompanyUser | test_create_user_invalid_company | Reject invalid company |
| TestCreateCompanyUser | test_create_user_weak_password | Reject weak password |
| TestGetCompanyUsers | test_get_all_company_users | Get all users |
| TestGetCompanyUsers | test_get_company_users_filtered | Filter by company |
| TestGetCompanyUsers | test_get_company_users_invalid_company | Handle invalid company |
| TestGetCompanyUsers | test_get_company_users_response_structure | Response structure |
| TestUpdateCompanyUser | test_update_user_permission_level | Update permission |
| TestUpdateCompanyUser | test_update_user_status | Update status |
| TestDeleteCompanyUser | test_delete_user_success | Delete user |
| TestDeleteCompanyUser | test_delete_nonexistent_user | Handle missing user |

### test_confirm_endpoints_split.py (16 tests)
| Test | Purpose |
|------|---------|
| `test_enterprise_confirm_success` | Enterprise confirm success flow |
| `test_enterprise_confirm_cancel` | Enterprise cancel flow |
| `test_enterprise_wrong_company_403` | Reject wrong company |
| `test_enterprise_missing_transaction_404` | Handle missing transaction |
| `test_enterprise_individual_user_403` | Reject individual user |
| `test_individual_confirm_success` | Individual confirm success |
| `test_individual_confirm_cancel` | Individual cancel flow |
| `test_individual_wrong_user_403` | Reject wrong user |
| `test_individual_missing_file_ids_400` | Require file IDs |
| `test_individual_empty_file_ids_400` | Reject empty file IDs |
| `test_individual_enterprise_user_403` | Reject enterprise user |
| `test_enterprise_no_file_search_called` | No file search for enterprise |
| `test_individual_no_file_search_called` | No file search for individual |
| `test_enterprise_no_documents_in_transaction_400` | Reject empty documents |
| `test_individual_authentication_required` | Require authentication |
| `test_enterprise_multiple_files` | Handle multiple files |

### test_confirm_square_payment.py (8 tests)
| Test | Purpose |
|------|---------|
| `test_1_valid_success_request` | Valid success request |
| `test_2_valid_failure_request` | Valid failure request |
| `test_3a_missing_square_transaction_id` | Require transaction ID |
| `test_3b_missing_status_field` | Require status field |
| `test_4_transaction_creation_on_success` | Create transaction on success |
| `test_5_no_transaction_on_failure` | No transaction on failure |
| `test_6a_success_response_format` | Success response format |
| `test_6b_failure_response_format` | Failure response format |

### test_dashboard.py (7 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestDashboardMetrics | test_get_dashboard_metrics_success | GET metrics returns 200 |
| TestDashboardMetrics | test_dashboard_metrics_structure | Response structure |
| TestDashboardMetrics | test_dashboard_metrics_data_types | Field data types |
| TestDashboardMetrics | test_dashboard_metrics_values | Metric values |
| TestDashboardMetrics | test_dashboard_metrics_match_database | Match DB values |
| TestEdgeCases | test_metrics_with_no_data | Handle empty data |
| TestEdgeCases | test_revenue_calculation_precision | Revenue precision |

### test_field_updates.py (28 tests)
Tests for updating subscription, usage period, company user, and company fields.

### test_individual_user_translation_mode_metadata.py (10 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestServerConnection | test_server_health_check | Server is healthy |
| TestServerConnection | test_mongodb_connection | DB connection works |
| TestTranslationModeInDatabase | test_existing_transactions_have_translation_mode | Mode stored in DB |
| TestTranslationModeInDatabase | test_query_transactions_by_translation_mode | Query by mode |
| TestTranslateUserAPIEndpoint | test_upload_endpoint_exists | Upload endpoint exists |
| TestTranslateUserAPIEndpoint | test_upload_endpoint_accepts_file_translation_modes | Accepts file modes |
| TestCodeImplementation | test_translate_user_has_translation_mode_in_initial_properties | Mode in properties |
| TestCodeImplementation | test_user_transaction_helper_logs_full_transaction | Full transaction logged |
| TestCodeImplementation | test_user_transaction_helper_logs_per_document_mode | Per-doc mode logged |
| TestEndToEndTranslationMode | test_upload_with_human_mode_stores_in_database | Human mode stored |

### test_nested_translation_flow.py (5 tests)
| Test | Purpose |
|------|---------|
| `test_create_transaction_with_nested_structure` | Create nested transaction |
| `test_update_document_in_transaction` | Update nested document |
| `test_get_transaction_list_returns_nested_structure` | List returns nested |
| `test_transaction_with_multiple_documents` | Multiple docs support |
| `test_datetime_timezone_handling` | Timezone handling |

### test_orders_api.py (18 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestAuthentication | test_orders_without_auth | Reject unauthenticated |
| TestAuthentication | test_orders_with_invalid_token | Reject invalid token |
| TestAuthentication | test_orders_with_valid_token | Accept valid token |
| TestFilters | test_filter_by_current_period | Filter current period |
| TestFilters | test_filter_by_previous_period | Filter previous period |
| TestFilters | test_filter_by_all_periods | All periods filter |
| TestFilters | test_filter_by_language_pair | Language pair filter |
| TestFilters | test_filter_by_status | Status filter |
| TestFilters | test_search_by_order_number | Search by order |
| TestFilters | test_search_by_user_email | Search by email |
| TestFilters | test_combined_filters | Combined filters |
| TestResponseStructure | test_response_structure | Response format |
| TestResponseStructure | test_period_structure | Period format |
| TestResponseStructure | test_order_fields | Order fields |
| TestResponseStructure | test_period_sorting | Period sorting |
| TestResponseStructure | test_order_sorting | Order sorting |
| TestEdgeCases | test_user_without_company | User without company |
| TestEdgeCases | test_invalid_date_period | Invalid date period |
| TestEdgeCases | test_invalid_status_filter | Invalid status |

### test_pricing_api.py (24 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestPricingCalculateEndpoint | test_calculate_individual_basic_small | Individual basic small tier |
| TestPricingCalculateEndpoint | test_calculate_individual_basic_medium | Individual basic medium tier |
| TestPricingCalculateEndpoint | test_calculate_individual_basic_large | Individual basic large tier |
| TestPricingCalculateEndpoint | test_calculate_individual_complex_formatted | Complex formatted pricing |
| TestPricingCalculateEndpoint | test_calculate_individual_human_translator | Human translator pricing |
| TestPricingCalculateEndpoint | test_calculate_enterprise_basic_small | Enterprise basic small tier |
| TestPricingCalculateEndpoint | test_calculate_enterprise_handwritten | Enterprise handwritten pricing |
| TestPricingCalculateEndpoint | test_calculate_defaults_to_basic | Default complexity is basic |
| TestPricingCalculateEndpoint | test_calculate_invalid_page_count | Reject invalid page count |
| TestPricingCalculateEndpoint | test_calculate_missing_required_fields | Reject missing fields |
| TestPricingCalculateGetEndpoint | test_calculate_get_individual | GET method works |
| TestPricingCalculateGetEndpoint | test_calculate_get_invalid_customer_type | Reject invalid type |
| TestPricingCalculateGetEndpoint | test_calculate_get_invalid_complexity | Reject invalid complexity |
| TestPricingTiersEndpoint | test_get_pricing_tiers | GET pricing tiers |
| TestPricingTiersEndpoint | test_get_pricing_tiers_volume_tiers | Volume tiers structure |
| TestComplexityLevelsEndpoint | test_get_complexity_levels | GET complexity levels |
| TestVolumeTiersEndpoint | test_get_volume_tiers | GET volume tiers |
| TestPricingBoundaryValues | test_boundary_1_page | 1 page boundary |
| TestPricingBoundaryValues | test_boundary_9_pages | 9 pages boundary |
| TestPricingBoundaryValues | test_boundary_10_pages | 10 pages boundary |
| TestPricingBoundaryValues | test_boundary_249_pages | 249 pages boundary |
| TestPricingBoundaryValues | test_boundary_250_pages | 250 pages boundary |
| TestPricingResponseFormat | test_response_has_all_fields | All response fields |
| TestPricingResponseFormat | test_response_types | Response field types |

### test_submit_api.py (10 tests)
| Test | Purpose |
|------|---------|
| `test_submit_endpoint_success` | Submit success |
| `test_submit_endpoint_without_transaction_id` | Require transaction ID |
| `test_submit_endpoint_missing_required_field` | Require all fields |
| `test_submit_endpoint_invalid_email` | Reject invalid email |
| `test_submit_endpoint_empty_file_name` | Reject empty filename |
| `test_submit_endpoint_invalid_url` | Reject invalid URL |
| `test_submit_endpoint_malformed_json` | Reject malformed JSON |
| `test_submit_endpoint_individual_customer` | Individual customer |
| `test_submit_endpoint_corporate_customer` | Corporate customer |
| `test_submit_endpoint_email_integration` | Email integration |

### test_submit_with_database.py (14 tests)
Tests submit functionality with real database integration.

### test_subscriptions_create.py (5 tests)
| Test | Purpose |
|------|---------|
| `test_create_subscription_with_existing_company_success` | Create with valid company |
| `test_create_subscription_with_nonexistent_company_fails` | Reject invalid company |
| `test_create_subscription_error_message_format` | Error message format |
| `test_create_subscription_case_sensitive_company_name` | Case sensitivity |
| `test_create_multiple_subscriptions_same_company` | Multiple subscriptions |

### test_subscriptions_edit.py (11 tests)
Tests for updating subscriptions and usage periods.

### test_transaction_confirm_square.py (27 tests)
Comprehensive Square transaction confirmation tests.

### test_translation_mode.py (18 tests)
| Class | Test | Purpose |
|-------|------|---------|
| TestTranslationModeEnumDefinition | test_translation_mode_enum_exists | Enum exists |
| TestTranslationModeEnumDefinition | test_translation_mode_has_automatic_value | Has automatic |
| TestTranslationModeEnumDefinition | test_translation_mode_has_human_value | Has human |
| TestTranslationModeEnumDefinition | test_translation_mode_has_formats_value | Has formats |
| TestTranslationModeEnumDefinition | test_translation_mode_has_handwriting_value | Has handwriting |
| TestTranslationModeEnumDefinition | test_translation_mode_is_string_enum | Is string enum |
| TestTranslateRequestModel | test_translate_request_accepts_translation_mode | Request accepts mode |
| TestTranslateRequestModel | test_translate_request_default_is_automatic | Default is automatic |
| TestTranslateRequestModel | test_translate_request_all_modes_valid | All modes valid |
| TestTranslateRequestModel | test_translate_request_invalid_mode_raises_error | Invalid mode error |
| TestTranslationModeStorage | test_translation_mode_field_is_string | Field is string |
| TestTranslationModeStorage | test_transaction_doc_structure_includes_mode | Doc includes mode |
| TestTranslationModeStorage | test_all_modes_are_valid_strings | All modes valid strings |
| TestCreateTransactionRecordWithMode | test_create_transaction_record_accepts_translation_mode | Create accepts mode |
| TestCreateTransactionRecordWithMode | test_create_transaction_record_has_default_mode | Create has default |
| TestCreateTransactionRecordWithMode | test_translate_request_mode_propagates_correctly | Mode propagates |
| TestTranslationModeEdgeCases | test_translation_mode_case_sensitivity | Case sensitivity |
| TestTranslationModeEdgeCases | test_translation_mode_empty_string_rejected | Reject empty |
| TestTranslationModeEdgeCases | test_translation_mode_accepts_string_values | Accept string values |

### test_user_transaction_creation.py (7 tests)
Transaction ID generation and index tests.

### test_user_transaction_metadata.py (14 tests)
User transaction metadata handling tests.

### test_user_transaction_structure.py (3 tests)
User transaction structure validation tests.

### test_user_transactions_multi_document.py (17 tests)
Multi-document transaction handling tests.

---

## Running Tests

### Run All Integration Tests
```bash
cd server
source venv/bin/activate
pytest tests/integration/ -v -s
```

### Run Specific Test File
```bash
pytest tests/integration/test_api_basic.py -v -s
```

### Run Single Test
```bash
pytest tests/integration/test_api_basic.py::TestCompanyAPI::test_get_companies -v -s
```

### Run with Coverage
```bash
pytest tests/integration/ -v --cov=app --cov-report=html
```

---

## Test Output Format

Each test outputs human-readable logs:

```
================================================================================
TEST: test_create_company_user
PURPOSE: Verify POST /api/company-users creates a new user for a company
STARTED: 2025-11-28 16:01:42
================================================================================

  STEP 1: Create test company in database collections
  [i] Created company: TEST_BASIC_TestCorp
  [OK] CHECK: Company exists in 'company' collection - PASS

  STEP 2: Create user via POST /api/company-users endpoint

  --> POST /api/company-users?company_name=TEST_BASIC_TestCorp
      Body: {...}
      Headers: {'X-Test-Name': 'test_create_company_user', ...}

  <-- + 201
      Response: {...}
  [OK] CHECK: Status code is 200 or 201 - PASS

--------------------------------------------------------------------------------
RESULT: PASSED
SUMMARY: User 'Test User' created successfully
DURATION: 0.19s
--------------------------------------------------------------------------------
```

---

*Generated: 2025-11-28*
