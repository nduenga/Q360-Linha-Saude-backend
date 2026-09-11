-- Q360 Health Underwriting & Pricing Core
-- Engineering Specification Pack v1.0
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- DOMAIN: PLATFORM | TABLE: tenant
CREATE TABLE IF NOT EXISTS tenant (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tenant_tenant ON tenant(tenant_id);

-- DOMAIN: PLATFORM | TABLE: tenant_setting
CREATE TABLE IF NOT EXISTS tenant_setting (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tenant_setting_tenant ON tenant_setting(tenant_id);

-- DOMAIN: PLATFORM | TABLE: business_unit
CREATE TABLE IF NOT EXISTS business_unit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_business_unit_tenant ON business_unit(tenant_id);

-- DOMAIN: PLATFORM | TABLE: branch
CREATE TABLE IF NOT EXISTS branch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_branch_tenant ON branch(tenant_id);

-- DOMAIN: PLATFORM | TABLE: sequence_counter
CREATE TABLE IF NOT EXISTS sequence_counter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_sequence_counter_tenant ON sequence_counter(tenant_id);

-- DOMAIN: PLATFORM | TABLE: feature_flag
CREATE TABLE IF NOT EXISTS feature_flag (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_feature_flag_tenant ON feature_flag(tenant_id);

-- DOMAIN: PLATFORM | TABLE: configuration_entry
CREATE TABLE IF NOT EXISTS configuration_entry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_configuration_entry_tenant ON configuration_entry(tenant_id);

-- DOMAIN: PLATFORM | TABLE: configuration_version
CREATE TABLE IF NOT EXISTS configuration_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_configuration_version_tenant ON configuration_version(tenant_id);

-- DOMAIN: PLATFORM | TABLE: localization_message
CREATE TABLE IF NOT EXISTS localization_message (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_localization_message_tenant ON localization_message(tenant_id);

-- DOMAIN: PLATFORM | TABLE: currency
CREATE TABLE IF NOT EXISTS currency (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_currency_tenant ON currency(tenant_id);

-- DOMAIN: PLATFORM | TABLE: exchange_rate
CREATE TABLE IF NOT EXISTS exchange_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_exchange_rate_tenant ON exchange_rate(tenant_id);

-- DOMAIN: PLATFORM | TABLE: country
CREATE TABLE IF NOT EXISTS country (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_country_tenant ON country(tenant_id);

-- DOMAIN: PLATFORM | TABLE: province
CREATE TABLE IF NOT EXISTS province (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_province_tenant ON province(tenant_id);

-- DOMAIN: PLATFORM | TABLE: municipality
CREATE TABLE IF NOT EXISTS municipality (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_municipality_tenant ON municipality(tenant_id);

-- DOMAIN: PLATFORM | TABLE: holiday_calendar
CREATE TABLE IF NOT EXISTS holiday_calendar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_holiday_calendar_tenant ON holiday_calendar(tenant_id);

-- DOMAIN: PLATFORM | TABLE: business_calendar
CREATE TABLE IF NOT EXISTS business_calendar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_business_calendar_tenant ON business_calendar(tenant_id);

-- DOMAIN: PLATFORM | TABLE: system_parameter
CREATE TABLE IF NOT EXISTS system_parameter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_system_parameter_tenant ON system_parameter(tenant_id);

-- DOMAIN: PLATFORM | TABLE: system_parameter_version
CREATE TABLE IF NOT EXISTS system_parameter_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_system_parameter_version_tenant ON system_parameter_version(tenant_id);

-- DOMAIN: PLATFORM | TABLE: reference_data_set
CREATE TABLE IF NOT EXISTS reference_data_set (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reference_data_set_tenant ON reference_data_set(tenant_id);

-- DOMAIN: PLATFORM | TABLE: reference_data_item
CREATE TABLE IF NOT EXISTS reference_data_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reference_data_item_tenant ON reference_data_item(tenant_id);

-- DOMAIN: IDENTITY | TABLE: app_user
CREATE TABLE IF NOT EXISTS app_user (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_app_user_tenant ON app_user(tenant_id);

-- DOMAIN: IDENTITY | TABLE: role
CREATE TABLE IF NOT EXISTS role (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_role_tenant ON role(tenant_id);

-- DOMAIN: IDENTITY | TABLE: permission
CREATE TABLE IF NOT EXISTS permission (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_permission_tenant ON permission(tenant_id);

-- DOMAIN: IDENTITY | TABLE: user_role
CREATE TABLE IF NOT EXISTS user_role (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_user_role_tenant ON user_role(tenant_id);

-- DOMAIN: IDENTITY | TABLE: role_permission
CREATE TABLE IF NOT EXISTS role_permission (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_role_permission_tenant ON role_permission(tenant_id);

-- DOMAIN: IDENTITY | TABLE: user_business_unit
CREATE TABLE IF NOT EXISTS user_business_unit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_user_business_unit_tenant ON user_business_unit(tenant_id);

-- DOMAIN: IDENTITY | TABLE: user_team
CREATE TABLE IF NOT EXISTS user_team (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_user_team_tenant ON user_team(tenant_id);

-- DOMAIN: IDENTITY | TABLE: team
CREATE TABLE IF NOT EXISTS team (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_team_tenant ON team(tenant_id);

-- DOMAIN: IDENTITY | TABLE: team_member
CREATE TABLE IF NOT EXISTS team_member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_team_member_tenant ON team_member(tenant_id);

-- DOMAIN: IDENTITY | TABLE: authority_profile
CREATE TABLE IF NOT EXISTS authority_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authority_profile_tenant ON authority_profile(tenant_id);

-- DOMAIN: IDENTITY | TABLE: authority_rule
CREATE TABLE IF NOT EXISTS authority_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authority_rule_tenant ON authority_rule(tenant_id);

-- DOMAIN: IDENTITY | TABLE: authority_delegation
CREATE TABLE IF NOT EXISTS authority_delegation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authority_delegation_tenant ON authority_delegation(tenant_id);

-- DOMAIN: IDENTITY | TABLE: login_audit
CREATE TABLE IF NOT EXISTS login_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_login_audit_tenant ON login_audit(tenant_id);

-- DOMAIN: IDENTITY | TABLE: user_session
CREATE TABLE IF NOT EXISTS user_session (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_user_session_tenant ON user_session(tenant_id);

-- DOMAIN: IDENTITY | TABLE: api_client
CREATE TABLE IF NOT EXISTS api_client (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_api_client_tenant ON api_client(tenant_id);

-- DOMAIN: IDENTITY | TABLE: api_scope
CREATE TABLE IF NOT EXISTS api_scope (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_api_scope_tenant ON api_scope(tenant_id);

-- DOMAIN: IDENTITY | TABLE: api_client_scope
CREATE TABLE IF NOT EXISTS api_client_scope (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_api_client_scope_tenant ON api_client_scope(tenant_id);

-- DOMAIN: IDENTITY | TABLE: service_account
CREATE TABLE IF NOT EXISTS service_account (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_service_account_tenant ON service_account(tenant_id);

-- DOMAIN: IDENTITY | TABLE: access_policy
CREATE TABLE IF NOT EXISTS access_policy (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_access_policy_tenant ON access_policy(tenant_id);

-- DOMAIN: IDENTITY | TABLE: access_policy_rule
CREATE TABLE IF NOT EXISTS access_policy_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_access_policy_rule_tenant ON access_policy_rule(tenant_id);

-- DOMAIN: PARTY | TABLE: party
CREATE TABLE IF NOT EXISTS party (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_tenant ON party(tenant_id);

-- DOMAIN: PARTY | TABLE: person
CREATE TABLE IF NOT EXISTS person (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  first_name VARCHAR(120) NOT NULL,
  last_name VARCHAR(120) NOT NULL,
  date_of_birth DATE ,
  gender_code VARCHAR(30) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_person_tenant ON person(tenant_id);

-- DOMAIN: PARTY | TABLE: organization
CREATE TABLE IF NOT EXISTS organization (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  legal_name VARCHAR(240) NOT NULL,
  trade_name VARCHAR(240) ,
  tax_id VARCHAR(80) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_tenant ON organization(tenant_id);

-- DOMAIN: PARTY | TABLE: party_identifier
CREATE TABLE IF NOT EXISTS party_identifier (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_identifier_tenant ON party_identifier(tenant_id);

-- DOMAIN: PARTY | TABLE: party_address
CREATE TABLE IF NOT EXISTS party_address (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_address_tenant ON party_address(tenant_id);

-- DOMAIN: PARTY | TABLE: party_contact
CREATE TABLE IF NOT EXISTS party_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_contact_tenant ON party_contact(tenant_id);

-- DOMAIN: PARTY | TABLE: party_bank_account
CREATE TABLE IF NOT EXISTS party_bank_account (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_bank_account_tenant ON party_bank_account(tenant_id);

-- DOMAIN: PARTY | TABLE: party_relationship
CREATE TABLE IF NOT EXISTS party_relationship (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_party_relationship_tenant ON party_relationship(tenant_id);

-- DOMAIN: PARTY | TABLE: person_document
CREATE TABLE IF NOT EXISTS person_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_person_document_tenant ON person_document(tenant_id);

-- DOMAIN: PARTY | TABLE: person_name_history
CREATE TABLE IF NOT EXISTS person_name_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_person_name_history_tenant ON person_name_history(tenant_id);

-- DOMAIN: PARTY | TABLE: person_employment
CREATE TABLE IF NOT EXISTS person_employment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_person_employment_tenant ON person_employment(tenant_id);

-- DOMAIN: PARTY | TABLE: person_occupation
CREATE TABLE IF NOT EXISTS person_occupation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_person_occupation_tenant ON person_occupation(tenant_id);

-- DOMAIN: PARTY | TABLE: organization_identifier
CREATE TABLE IF NOT EXISTS organization_identifier (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_identifier_tenant ON organization_identifier(tenant_id);

-- DOMAIN: PARTY | TABLE: organization_contact
CREATE TABLE IF NOT EXISTS organization_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_contact_tenant ON organization_contact(tenant_id);

-- DOMAIN: PARTY | TABLE: organization_address
CREATE TABLE IF NOT EXISTS organization_address (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_address_tenant ON organization_address(tenant_id);

-- DOMAIN: PARTY | TABLE: organization_sector
CREATE TABLE IF NOT EXISTS organization_sector (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_sector_tenant ON organization_sector(tenant_id);

-- DOMAIN: PARTY | TABLE: organization_financial_profile
CREATE TABLE IF NOT EXISTS organization_financial_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_organization_financial_profile_tenant ON organization_financial_profile(tenant_id);

-- DOMAIN: PARTY | TABLE: customer
CREATE TABLE IF NOT EXISTS customer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_tenant ON customer(tenant_id);

-- DOMAIN: PARTY | TABLE: customer_segment
CREATE TABLE IF NOT EXISTS customer_segment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_segment_tenant ON customer_segment(tenant_id);

-- DOMAIN: PARTY | TABLE: customer_status_history
CREATE TABLE IF NOT EXISTS customer_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_status_history_tenant ON customer_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_customer_status_history_status ON customer_status_history(tenant_id, status);

-- DOMAIN: PARTY | TABLE: customer_note
CREATE TABLE IF NOT EXISTS customer_note (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_note_tenant ON customer_note(tenant_id);

-- DOMAIN: PARTY | TABLE: customer_tag
CREATE TABLE IF NOT EXISTS customer_tag (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_tag_tenant ON customer_tag(tenant_id);

-- DOMAIN: PARTY | TABLE: customer_tag_link
CREATE TABLE IF NOT EXISTS customer_tag_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_customer_tag_link_tenant ON customer_tag_link(tenant_id);

-- DOMAIN: PARTY | TABLE: broker
CREATE TABLE IF NOT EXISTS broker (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_broker_tenant ON broker(tenant_id);

-- DOMAIN: PARTY | TABLE: broker_license
CREATE TABLE IF NOT EXISTS broker_license (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_broker_license_tenant ON broker_license(tenant_id);

-- DOMAIN: PARTY | TABLE: broker_contact
CREATE TABLE IF NOT EXISTS broker_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_broker_contact_tenant ON broker_contact(tenant_id);

-- DOMAIN: PARTY | TABLE: broker_commission_profile
CREATE TABLE IF NOT EXISTS broker_commission_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_broker_commission_profile_tenant ON broker_commission_profile(tenant_id);

-- DOMAIN: PARTY | TABLE: intermediary_assignment
CREATE TABLE IF NOT EXISTS intermediary_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_intermediary_assignment_tenant ON intermediary_assignment(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product
CREATE TABLE IF NOT EXISTS product (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_code VARCHAR(80) NOT NULL,
  product_name VARCHAR(240) NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_tenant ON product(tenant_id);
CREATE INDEX IF NOT EXISTS idx_product_status ON product(tenant_id, status);

-- DOMAIN: PRODUCT | TABLE: product_version
CREATE TABLE IF NOT EXISTS product_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_version_tenant ON product_version(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_segment
CREATE TABLE IF NOT EXISTS product_segment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_segment_tenant ON product_segment(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_version_segment
CREATE TABLE IF NOT EXISTS product_version_segment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_version_segment_tenant ON product_version_segment(tenant_id);

-- DOMAIN: PRODUCT | TABLE: plan
CREATE TABLE IF NOT EXISTS plan (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_plan_tenant ON plan(tenant_id);

-- DOMAIN: PRODUCT | TABLE: plan_version
CREATE TABLE IF NOT EXISTS plan_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_plan_version_tenant ON plan_version(tenant_id);

-- DOMAIN: PRODUCT | TABLE: coverage
CREATE TABLE IF NOT EXISTS coverage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_coverage_tenant ON coverage(tenant_id);

-- DOMAIN: PRODUCT | TABLE: coverage_version
CREATE TABLE IF NOT EXISTS coverage_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_coverage_version_tenant ON coverage_version(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit
CREATE TABLE IF NOT EXISTS benefit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_tenant ON benefit(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_version
CREATE TABLE IF NOT EXISTS benefit_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_version_tenant ON benefit_version(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_limit
CREATE TABLE IF NOT EXISTS benefit_limit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_limit_tenant ON benefit_limit(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_sublimit
CREATE TABLE IF NOT EXISTS benefit_sublimit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_sublimit_tenant ON benefit_sublimit(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_deductible
CREATE TABLE IF NOT EXISTS benefit_deductible (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_deductible_tenant ON benefit_deductible(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_copayment
CREATE TABLE IF NOT EXISTS benefit_copayment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_copayment_tenant ON benefit_copayment(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_waiting_period
CREATE TABLE IF NOT EXISTS benefit_waiting_period (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_waiting_period_tenant ON benefit_waiting_period(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_exclusion
CREATE TABLE IF NOT EXISTS benefit_exclusion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_exclusion_tenant ON benefit_exclusion(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_territory
CREATE TABLE IF NOT EXISTS benefit_territory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_territory_tenant ON benefit_territory(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_network_rule
CREATE TABLE IF NOT EXISTS benefit_network_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_network_rule_tenant ON benefit_network_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_age_rule
CREATE TABLE IF NOT EXISTS benefit_age_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_age_rule_tenant ON benefit_age_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: benefit_eligibility_rule
CREATE TABLE IF NOT EXISTS benefit_eligibility_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_benefit_eligibility_rule_tenant ON benefit_eligibility_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_rule
CREATE TABLE IF NOT EXISTS product_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_rule_tenant ON product_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_rule_version
CREATE TABLE IF NOT EXISTS product_rule_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_rule_version_tenant ON product_rule_version(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_validation_result
CREATE TABLE IF NOT EXISTS product_validation_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_validation_result_tenant ON product_validation_result(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_document_requirement
CREATE TABLE IF NOT EXISTS product_document_requirement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_document_requirement_tenant ON product_document_requirement(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_questionnaire_link
CREATE TABLE IF NOT EXISTS product_questionnaire_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_questionnaire_link_tenant ON product_questionnaire_link(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_reinsurance_link
CREATE TABLE IF NOT EXISTS product_reinsurance_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_reinsurance_link_tenant ON product_reinsurance_link(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_tpa_link
CREATE TABLE IF NOT EXISTS product_tpa_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_tpa_link_tenant ON product_tpa_link(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_tax_rule
CREATE TABLE IF NOT EXISTS product_tax_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_tax_rule_tenant ON product_tax_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_fee_rule
CREATE TABLE IF NOT EXISTS product_fee_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_fee_rule_tenant ON product_fee_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_commission_rule
CREATE TABLE IF NOT EXISTS product_commission_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_commission_rule_tenant ON product_commission_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_currency_rule
CREATE TABLE IF NOT EXISTS product_currency_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_currency_rule_tenant ON product_currency_rule(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_sales_channel
CREATE TABLE IF NOT EXISTS product_sales_channel (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_sales_channel_tenant ON product_sales_channel(tenant_id);

-- DOMAIN: PRODUCT | TABLE: product_status_history
CREATE TABLE IF NOT EXISTS product_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  product_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_product_status_history_tenant ON product_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_product_status_history_status ON product_status_history(tenant_id, status);

-- DOMAIN: MEDICAL | TABLE: medical_condition
CREATE TABLE IF NOT EXISTS medical_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_condition_tenant ON medical_condition(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_condition_alias
CREATE TABLE IF NOT EXISTS medical_condition_alias (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_condition_alias_tenant ON medical_condition_alias(tenant_id);

-- DOMAIN: MEDICAL | TABLE: diagnosis_system
CREATE TABLE IF NOT EXISTS diagnosis_system (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_diagnosis_system_tenant ON diagnosis_system(tenant_id);

-- DOMAIN: MEDICAL | TABLE: diagnosis_catalogue
CREATE TABLE IF NOT EXISTS diagnosis_catalogue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_diagnosis_catalogue_tenant ON diagnosis_catalogue(tenant_id);

-- DOMAIN: MEDICAL | TABLE: diagnosis_code
CREATE TABLE IF NOT EXISTS diagnosis_code (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  diagnosis_system_id UUID NOT NULL,
  code VARCHAR(40) NOT NULL,
  description TEXT NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_diagnosis_code_tenant ON diagnosis_code(tenant_id);

-- DOMAIN: MEDICAL | TABLE: diagnosis_mapping
CREATE TABLE IF NOT EXISTS diagnosis_mapping (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_diagnosis_mapping_tenant ON diagnosis_mapping(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_severity
CREATE TABLE IF NOT EXISTS medical_severity (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_severity_tenant ON medical_severity(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_risk_factor
CREATE TABLE IF NOT EXISTS medical_risk_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_risk_factor_tenant ON medical_risk_factor(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_risk_factor_version
CREATE TABLE IF NOT EXISTS medical_risk_factor_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_risk_factor_version_tenant ON medical_risk_factor_version(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_loading_rule
CREATE TABLE IF NOT EXISTS medical_loading_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_loading_rule_tenant ON medical_loading_rule(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_exclusion_rule
CREATE TABLE IF NOT EXISTS medical_exclusion_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_exclusion_rule_tenant ON medical_exclusion_rule(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_waiting_rule
CREATE TABLE IF NOT EXISTS medical_waiting_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_waiting_rule_tenant ON medical_waiting_rule(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_evidence_type
CREATE TABLE IF NOT EXISTS medical_evidence_type (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_evidence_type_tenant ON medical_evidence_type(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_evidence_requirement
CREATE TABLE IF NOT EXISTS medical_evidence_requirement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_evidence_requirement_tenant ON medical_evidence_requirement(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_guideline
CREATE TABLE IF NOT EXISTS medical_guideline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_guideline_tenant ON medical_guideline(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_guideline_version
CREATE TABLE IF NOT EXISTS medical_guideline_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_guideline_version_tenant ON medical_guideline_version(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_comorbidity_rule
CREATE TABLE IF NOT EXISTS medical_comorbidity_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_comorbidity_rule_tenant ON medical_comorbidity_rule(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_score_band
CREATE TABLE IF NOT EXISTS medical_score_band (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_score_band_tenant ON medical_score_band(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_score_weight
CREATE TABLE IF NOT EXISTS medical_score_weight (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_score_weight_tenant ON medical_score_weight(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_assessment
CREATE TABLE IF NOT EXISTS medical_assessment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_assessment_tenant ON medical_assessment(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_assessment_condition
CREATE TABLE IF NOT EXISTS medical_assessment_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_assessment_condition_tenant ON medical_assessment_condition(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_assessment_factor
CREATE TABLE IF NOT EXISTS medical_assessment_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_assessment_factor_tenant ON medical_assessment_factor(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_assessment_result
CREATE TABLE IF NOT EXISTS medical_assessment_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_assessment_result_tenant ON medical_assessment_result(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_loading
CREATE TABLE IF NOT EXISTS medical_loading (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_loading_tenant ON medical_loading(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_exclusion
CREATE TABLE IF NOT EXISTS medical_exclusion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_exclusion_tenant ON medical_exclusion(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_waiting_period
CREATE TABLE IF NOT EXISTS medical_waiting_period (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_waiting_period_tenant ON medical_waiting_period(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_referral
CREATE TABLE IF NOT EXISTS medical_referral (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_referral_tenant ON medical_referral(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_review
CREATE TABLE IF NOT EXISTS medical_review (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_review_tenant ON medical_review(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_review_attachment
CREATE TABLE IF NOT EXISTS medical_review_attachment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_review_attachment_tenant ON medical_review_attachment(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_board_decision
CREATE TABLE IF NOT EXISTS medical_board_decision (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_board_decision_tenant ON medical_board_decision(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_consent
CREATE TABLE IF NOT EXISTS medical_consent (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_consent_tenant ON medical_consent(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_access_log
CREATE TABLE IF NOT EXISTS medical_access_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_access_log_tenant ON medical_access_log(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_vault_record
CREATE TABLE IF NOT EXISTS medical_vault_record (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_vault_record_tenant ON medical_vault_record(tenant_id);

-- DOMAIN: MEDICAL | TABLE: medical_vault_key_ref
CREATE TABLE IF NOT EXISTS medical_vault_key_ref (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_medical_vault_key_ref_tenant ON medical_vault_key_ref(tenant_id);

-- DOMAIN: MEDICAL | TABLE: lab_result
CREATE TABLE IF NOT EXISTS lab_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_lab_result_tenant ON lab_result(tenant_id);

-- DOMAIN: MEDICAL | TABLE: clinical_measurement
CREATE TABLE IF NOT EXISTS clinical_measurement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_clinical_measurement_tenant ON clinical_measurement(tenant_id);

-- DOMAIN: MEDICAL | TABLE: lifestyle_factor
CREATE TABLE IF NOT EXISTS lifestyle_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_lifestyle_factor_tenant ON lifestyle_factor(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire
CREATE TABLE IF NOT EXISTS questionnaire (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_tenant ON questionnaire(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_version
CREATE TABLE IF NOT EXISTS questionnaire_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_version_tenant ON questionnaire_version(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_section
CREATE TABLE IF NOT EXISTS questionnaire_section (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_section_tenant ON questionnaire_section(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question
CREATE TABLE IF NOT EXISTS question (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  question_key VARCHAR(100) NOT NULL,
  question_type VARCHAR(40) NOT NULL,
  prompt TEXT NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_tenant ON question(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question_version
CREATE TABLE IF NOT EXISTS question_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_version_tenant ON question_version(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question_option
CREATE TABLE IF NOT EXISTS question_option (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_option_tenant ON question_option(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question_condition
CREATE TABLE IF NOT EXISTS question_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_condition_tenant ON question_condition(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question_validation_rule
CREATE TABLE IF NOT EXISTS question_validation_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_validation_rule_tenant ON question_validation_rule(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_assignment
CREATE TABLE IF NOT EXISTS questionnaire_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_assignment_tenant ON questionnaire_assignment(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_session
CREATE TABLE IF NOT EXISTS questionnaire_session (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_session_tenant ON questionnaire_session(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_response
CREATE TABLE IF NOT EXISTS questionnaire_response (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_response_tenant ON questionnaire_response(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: question_response
CREATE TABLE IF NOT EXISTS question_response (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_question_response_tenant ON question_response(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: response_attachment
CREATE TABLE IF NOT EXISTS response_attachment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_response_attachment_tenant ON response_attachment(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_score
CREATE TABLE IF NOT EXISTS questionnaire_score (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_score_tenant ON questionnaire_score(tenant_id);

-- DOMAIN: QUESTIONNAIRE | TABLE: questionnaire_audit
CREATE TABLE IF NOT EXISTS questionnaire_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_audit_tenant ON questionnaire_audit(tenant_id);

-- DOMAIN: MEMBER | TABLE: corporate_group
CREATE TABLE IF NOT EXISTS corporate_group (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_corporate_group_tenant ON corporate_group(tenant_id);

-- DOMAIN: MEMBER | TABLE: group_contract_profile
CREATE TABLE IF NOT EXISTS group_contract_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_contract_profile_tenant ON group_contract_profile(tenant_id);

-- DOMAIN: MEMBER | TABLE: eligibility_population
CREATE TABLE IF NOT EXISTS eligibility_population (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_population_tenant ON eligibility_population(tenant_id);

-- DOMAIN: MEMBER | TABLE: eligibility_rule
CREATE TABLE IF NOT EXISTS eligibility_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_rule_tenant ON eligibility_rule(tenant_id);

-- DOMAIN: MEMBER | TABLE: eligibility_rule_version
CREATE TABLE IF NOT EXISTS eligibility_rule_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_rule_version_tenant ON eligibility_rule_version(tenant_id);

-- DOMAIN: MEMBER | TABLE: member
CREATE TABLE IF NOT EXISTS member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  person_id UUID NOT NULL,
  group_id UUID ,
  member_number VARCHAR(60) NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_tenant ON member(tenant_id);
CREATE INDEX IF NOT EXISTS idx_member_status ON member(tenant_id, status);

-- DOMAIN: MEMBER | TABLE: member_identifier
CREATE TABLE IF NOT EXISTS member_identifier (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_identifier_tenant ON member_identifier(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_status_history
CREATE TABLE IF NOT EXISTS member_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_status_history_tenant ON member_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_member_status_history_status ON member_status_history(tenant_id, status);

-- DOMAIN: MEMBER | TABLE: member_plan_assignment
CREATE TABLE IF NOT EXISTS member_plan_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_plan_assignment_tenant ON member_plan_assignment(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_coverage_assignment
CREATE TABLE IF NOT EXISTS member_coverage_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_coverage_assignment_tenant ON member_coverage_assignment(tenant_id);

-- DOMAIN: MEMBER | TABLE: dependent
CREATE TABLE IF NOT EXISTS dependent (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dependent_tenant ON dependent(tenant_id);

-- DOMAIN: MEMBER | TABLE: dependent_relationship
CREATE TABLE IF NOT EXISTS dependent_relationship (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dependent_relationship_tenant ON dependent_relationship(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_movement
CREATE TABLE IF NOT EXISTS member_movement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_movement_tenant ON member_movement(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_movement_batch
CREATE TABLE IF NOT EXISTS member_movement_batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_movement_batch_tenant ON member_movement_batch(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_import_batch
CREATE TABLE IF NOT EXISTS member_import_batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_import_batch_tenant ON member_import_batch(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_import_row
CREATE TABLE IF NOT EXISTS member_import_row (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_import_row_tenant ON member_import_row(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_import_error
CREATE TABLE IF NOT EXISTS member_import_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_import_error_tenant ON member_import_error(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_month_exposure
CREATE TABLE IF NOT EXISTS member_month_exposure (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_month_exposure_tenant ON member_month_exposure(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_accumulation
CREATE TABLE IF NOT EXISTS member_accumulation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_accumulation_tenant ON member_accumulation(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_benefit_balance
CREATE TABLE IF NOT EXISTS member_benefit_balance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_benefit_balance_tenant ON member_benefit_balance(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_benefit_usage
CREATE TABLE IF NOT EXISTS member_benefit_usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_benefit_usage_tenant ON member_benefit_usage(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_card
CREATE TABLE IF NOT EXISTS member_card (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_card_tenant ON member_card(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_tpa_reference
CREATE TABLE IF NOT EXISTS member_tpa_reference (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_tpa_reference_tenant ON member_tpa_reference(tenant_id);

-- DOMAIN: MEMBER | TABLE: member_consent
CREATE TABLE IF NOT EXISTS member_consent (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_consent_tenant ON member_consent(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_underwriting_case
CREATE TABLE IF NOT EXISTS group_underwriting_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_underwriting_case_tenant ON group_underwriting_case(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_population_snapshot
CREATE TABLE IF NOT EXISTS group_population_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_population_snapshot_tenant ON group_population_snapshot(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: demographic_snapshot
CREATE TABLE IF NOT EXISTS demographic_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_demographic_snapshot_tenant ON demographic_snapshot(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: age_distribution
CREATE TABLE IF NOT EXISTS age_distribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_age_distribution_tenant ON age_distribution(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: gender_distribution
CREATE TABLE IF NOT EXISTS gender_distribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_gender_distribution_tenant ON gender_distribution(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: relationship_distribution
CREATE TABLE IF NOT EXISTS relationship_distribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_relationship_distribution_tenant ON relationship_distribution(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: occupation_distribution
CREATE TABLE IF NOT EXISTS occupation_distribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_occupation_distribution_tenant ON occupation_distribution(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: location_distribution
CREATE TABLE IF NOT EXISTS location_distribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_location_distribution_tenant ON location_distribution(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: family_composition_metric
CREATE TABLE IF NOT EXISTS family_composition_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_family_composition_metric_tenant ON family_composition_metric(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: participation_metric
CREATE TABLE IF NOT EXISTS participation_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_participation_metric_tenant ON participation_metric(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: anti_selection_rule
CREATE TABLE IF NOT EXISTS anti_selection_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_anti_selection_rule_tenant ON anti_selection_rule(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: anti_selection_rule_version
CREATE TABLE IF NOT EXISTS anti_selection_rule_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_anti_selection_rule_version_tenant ON anti_selection_rule_version(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: anti_selection_result
CREATE TABLE IF NOT EXISTS anti_selection_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_anti_selection_result_tenant ON anti_selection_result(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: anti_selection_alert
CREATE TABLE IF NOT EXISTS anti_selection_alert (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_anti_selection_alert_tenant ON anti_selection_alert(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_risk_factor
CREATE TABLE IF NOT EXISTS group_risk_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_risk_factor_tenant ON group_risk_factor(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_risk_score
CREATE TABLE IF NOT EXISTS group_risk_score (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_risk_score_tenant ON group_risk_score(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_medical_aggregation
CREATE TABLE IF NOT EXISTS group_medical_aggregation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_medical_aggregation_tenant ON group_medical_aggregation(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_underwriting_result
CREATE TABLE IF NOT EXISTS group_underwriting_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_underwriting_result_tenant ON group_underwriting_result(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_data_quality_score
CREATE TABLE IF NOT EXISTS group_data_quality_score (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_data_quality_score_tenant ON group_data_quality_score(tenant_id);

-- DOMAIN: GROUP_UW | TABLE: group_data_quality_issue
CREATE TABLE IF NOT EXISTS group_data_quality_issue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_data_quality_issue_tenant ON group_data_quality_issue(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider
CREATE TABLE IF NOT EXISTS provider (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_tenant ON provider(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_facility
CREATE TABLE IF NOT EXISTS provider_facility (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_facility_tenant ON provider_facility(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_identifier
CREATE TABLE IF NOT EXISTS provider_identifier (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_identifier_tenant ON provider_identifier(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_license
CREATE TABLE IF NOT EXISTS provider_license (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_license_tenant ON provider_license(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_specialty
CREATE TABLE IF NOT EXISTS provider_specialty (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_specialty_tenant ON provider_specialty(tenant_id);

-- DOMAIN: PROVIDER | TABLE: specialty
CREATE TABLE IF NOT EXISTS specialty (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_specialty_tenant ON specialty(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_specialty_link
CREATE TABLE IF NOT EXISTS provider_specialty_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_specialty_link_tenant ON provider_specialty_link(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_contract
CREATE TABLE IF NOT EXISTS provider_contract (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_contract_tenant ON provider_contract(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_contract_version
CREATE TABLE IF NOT EXISTS provider_contract_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_contract_version_tenant ON provider_contract_version(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_network
CREATE TABLE IF NOT EXISTS provider_network (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_network_tenant ON provider_network(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_network_version
CREATE TABLE IF NOT EXISTS provider_network_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_network_version_tenant ON provider_network_version(tenant_id);

-- DOMAIN: PROVIDER | TABLE: network_provider
CREATE TABLE IF NOT EXISTS network_provider (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_network_provider_tenant ON network_provider(tenant_id);

-- DOMAIN: PROVIDER | TABLE: network_rule
CREATE TABLE IF NOT EXISTS network_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_network_rule_tenant ON network_rule(tenant_id);

-- DOMAIN: PROVIDER | TABLE: network_cost_index
CREATE TABLE IF NOT EXISTS network_cost_index (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_network_cost_index_tenant ON network_cost_index(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_tariff
CREATE TABLE IF NOT EXISTS provider_tariff (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_tariff_tenant ON provider_tariff(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_tariff_version
CREATE TABLE IF NOT EXISTS provider_tariff_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_tariff_version_tenant ON provider_tariff_version(tenant_id);

-- DOMAIN: PROVIDER | TABLE: tariff_item
CREATE TABLE IF NOT EXISTS tariff_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tariff_item_tenant ON tariff_item(tenant_id);

-- DOMAIN: PROVIDER | TABLE: procedure_catalogue
CREATE TABLE IF NOT EXISTS procedure_catalogue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_procedure_catalogue_tenant ON procedure_catalogue(tenant_id);

-- DOMAIN: PROVIDER | TABLE: procedure_code
CREATE TABLE IF NOT EXISTS procedure_code (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_procedure_code_tenant ON procedure_code(tenant_id);

-- DOMAIN: PROVIDER | TABLE: procedure_mapping
CREATE TABLE IF NOT EXISTS procedure_mapping (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_procedure_mapping_tenant ON procedure_mapping(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_performance_metric
CREATE TABLE IF NOT EXISTS provider_performance_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_performance_metric_tenant ON provider_performance_metric(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_cost_metric
CREATE TABLE IF NOT EXISTS provider_cost_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_cost_metric_tenant ON provider_cost_metric(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_concentration_metric
CREATE TABLE IF NOT EXISTS provider_concentration_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_concentration_metric_tenant ON provider_concentration_metric(tenant_id);

-- DOMAIN: PROVIDER | TABLE: provider_status_history
CREATE TABLE IF NOT EXISTS provider_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_status_history_tenant ON provider_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_provider_status_history_status ON provider_status_history(tenant_id, status);

-- DOMAIN: PROVIDER | TABLE: provider_tpa_reference
CREATE TABLE IF NOT EXISTS provider_tpa_reference (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_tpa_reference_tenant ON provider_tpa_reference(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim
CREATE TABLE IF NOT EXISTS claim (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  claim_number VARCHAR(60) NOT NULL,
  service_date DATE NOT NULL,
  reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_tenant ON claim(tenant_id);
CREATE INDEX IF NOT EXISTS idx_claim_status ON claim(tenant_id, status);

-- DOMAIN: CLAIMS | TABLE: claim_line
CREATE TABLE IF NOT EXISTS claim_line (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_line_tenant ON claim_line(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_status_history
CREATE TABLE IF NOT EXISTS claim_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_status_history_tenant ON claim_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_claim_status_history_status ON claim_status_history(tenant_id, status);

-- DOMAIN: CLAIMS | TABLE: claim_member
CREATE TABLE IF NOT EXISTS claim_member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_member_tenant ON claim_member(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_provider
CREATE TABLE IF NOT EXISTS claim_provider (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  claim_id UUID ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_provider_tenant ON claim_provider(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_diagnosis
CREATE TABLE IF NOT EXISTS claim_diagnosis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_diagnosis_tenant ON claim_diagnosis(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_procedure
CREATE TABLE IF NOT EXISTS claim_procedure (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_procedure_tenant ON claim_procedure(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_benefit_allocation
CREATE TABLE IF NOT EXISTS claim_benefit_allocation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_benefit_allocation_tenant ON claim_benefit_allocation(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_payment
CREATE TABLE IF NOT EXISTS claim_payment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_payment_tenant ON claim_payment(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_reserve
CREATE TABLE IF NOT EXISTS claim_reserve (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_reserve_tenant ON claim_reserve(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_recovery
CREATE TABLE IF NOT EXISTS claim_recovery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_recovery_tenant ON claim_recovery(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_currency_amount
CREATE TABLE IF NOT EXISTS claim_currency_amount (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_currency_amount_tenant ON claim_currency_amount(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_document
CREATE TABLE IF NOT EXISTS claim_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_document_tenant ON claim_document(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_note
CREATE TABLE IF NOT EXISTS claim_note (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_note_tenant ON claim_note(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_import_batch
CREATE TABLE IF NOT EXISTS claim_import_batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_import_batch_tenant ON claim_import_batch(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_import_file
CREATE TABLE IF NOT EXISTS claim_import_file (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_import_file_tenant ON claim_import_file(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_import_row
CREATE TABLE IF NOT EXISTS claim_import_row (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_import_row_tenant ON claim_import_row(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_import_error
CREATE TABLE IF NOT EXISTS claim_import_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_import_error_tenant ON claim_import_error(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_normalization_map
CREATE TABLE IF NOT EXISTS claim_normalization_map (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_normalization_map_tenant ON claim_normalization_map(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_duplicate_candidate
CREATE TABLE IF NOT EXISTS claim_duplicate_candidate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_duplicate_candidate_tenant ON claim_duplicate_candidate(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claim_metric_snapshot
CREATE TABLE IF NOT EXISTS claim_metric_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_metric_snapshot_tenant ON claim_metric_snapshot(tenant_id);

-- DOMAIN: CLAIMS | TABLE: loss_ratio_metric
CREATE TABLE IF NOT EXISTS loss_ratio_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_loss_ratio_metric_tenant ON loss_ratio_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: pmpm_metric
CREATE TABLE IF NOT EXISTS pmpm_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pmpm_metric_tenant ON pmpm_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: frequency_metric
CREATE TABLE IF NOT EXISTS frequency_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_frequency_metric_tenant ON frequency_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: severity_metric
CREATE TABLE IF NOT EXISTS severity_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_severity_metric_tenant ON severity_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: utilisation_metric
CREATE TABLE IF NOT EXISTS utilisation_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_utilisation_metric_tenant ON utilisation_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claimant_rate_metric
CREATE TABLE IF NOT EXISTS claimant_rate_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claimant_rate_metric_tenant ON claimant_rate_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: cost_driver_metric
CREATE TABLE IF NOT EXISTS cost_driver_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_cost_driver_metric_tenant ON cost_driver_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: large_claim_threshold
CREATE TABLE IF NOT EXISTS large_claim_threshold (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_large_claim_threshold_tenant ON large_claim_threshold(tenant_id);

-- DOMAIN: CLAIMS | TABLE: large_claim_event
CREATE TABLE IF NOT EXISTS large_claim_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_large_claim_event_tenant ON large_claim_event(tenant_id);

-- DOMAIN: CLAIMS | TABLE: large_claim_normalization
CREATE TABLE IF NOT EXISTS large_claim_normalization (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_large_claim_normalization_tenant ON large_claim_normalization(tenant_id);

-- DOMAIN: CLAIMS | TABLE: chronic_condition_metric
CREATE TABLE IF NOT EXISTS chronic_condition_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_chronic_condition_metric_tenant ON chronic_condition_metric(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claims_experience_period
CREATE TABLE IF NOT EXISTS claims_experience_period (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claims_experience_period_tenant ON claims_experience_period(tenant_id);

-- DOMAIN: CLAIMS | TABLE: claims_experience_result
CREATE TABLE IF NOT EXISTS claims_experience_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claims_experience_result_tenant ON claims_experience_result(tenant_id);

-- DOMAIN: CLAIMS | TABLE: credibility_model
CREATE TABLE IF NOT EXISTS credibility_model (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_credibility_model_tenant ON credibility_model(tenant_id);

-- DOMAIN: CLAIMS | TABLE: credibility_parameter
CREATE TABLE IF NOT EXISTS credibility_parameter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_credibility_parameter_tenant ON credibility_parameter(tenant_id);

-- DOMAIN: CLAIMS | TABLE: experience_rate
CREATE TABLE IF NOT EXISTS experience_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_experience_rate_tenant ON experience_rate(tenant_id);

-- DOMAIN: CLAIMS | TABLE: manual_rate
CREATE TABLE IF NOT EXISTS manual_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_manual_rate_tenant ON manual_rate(tenant_id);

-- DOMAIN: CLAIMS | TABLE: experience_rating_result
CREATE TABLE IF NOT EXISTS experience_rating_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_experience_rating_result_tenant ON experience_rating_result(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_case
CREATE TABLE IF NOT EXISTS pricing_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_case_tenant ON pricing_case(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_context_snapshot
CREATE TABLE IF NOT EXISTS pricing_context_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_context_snapshot_tenant ON pricing_context_snapshot(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_parameter_set
CREATE TABLE IF NOT EXISTS pricing_parameter_set (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_parameter_set_tenant ON pricing_parameter_set(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_parameter_version
CREATE TABLE IF NOT EXISTS pricing_parameter_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_parameter_version_tenant ON pricing_parameter_version(tenant_id);

-- DOMAIN: PRICING | TABLE: rating_factor
CREATE TABLE IF NOT EXISTS rating_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_rating_factor_tenant ON rating_factor(tenant_id);

-- DOMAIN: PRICING | TABLE: rating_factor_version
CREATE TABLE IF NOT EXISTS rating_factor_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_rating_factor_version_tenant ON rating_factor_version(tenant_id);

-- DOMAIN: PRICING | TABLE: rating_factor_band
CREATE TABLE IF NOT EXISTS rating_factor_band (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_rating_factor_band_tenant ON rating_factor_band(tenant_id);

-- DOMAIN: PRICING | TABLE: manual_rate_table
CREATE TABLE IF NOT EXISTS manual_rate_table (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_manual_rate_table_tenant ON manual_rate_table(tenant_id);

-- DOMAIN: PRICING | TABLE: manual_rate_item
CREATE TABLE IF NOT EXISTS manual_rate_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_manual_rate_item_tenant ON manual_rate_item(tenant_id);

-- DOMAIN: PRICING | TABLE: trend_factor
CREATE TABLE IF NOT EXISTS trend_factor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_trend_factor_tenant ON trend_factor(tenant_id);

-- DOMAIN: PRICING | TABLE: trend_factor_version
CREATE TABLE IF NOT EXISTS trend_factor_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_trend_factor_version_tenant ON trend_factor_version(tenant_id);

-- DOMAIN: PRICING | TABLE: trend_scenario
CREATE TABLE IF NOT EXISTS trend_scenario (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_trend_scenario_tenant ON trend_scenario(tenant_id);

-- DOMAIN: PRICING | TABLE: network_pricing_rule
CREATE TABLE IF NOT EXISTS network_pricing_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_network_pricing_rule_tenant ON network_pricing_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: network_pricing_result
CREATE TABLE IF NOT EXISTS network_pricing_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_network_pricing_result_tenant ON network_pricing_result(tenant_id);

-- DOMAIN: PRICING | TABLE: expense_rule
CREATE TABLE IF NOT EXISTS expense_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_expense_rule_tenant ON expense_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: tpa_cost_rule
CREATE TABLE IF NOT EXISTS tpa_cost_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_cost_rule_tenant ON tpa_cost_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: commission_rule
CREATE TABLE IF NOT EXISTS commission_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_commission_rule_tenant ON commission_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: risk_margin_rule
CREATE TABLE IF NOT EXISTS risk_margin_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_risk_margin_rule_tenant ON risk_margin_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: profit_margin_rule
CREATE TABLE IF NOT EXISTS profit_margin_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_profit_margin_rule_tenant ON profit_margin_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: tax_charge_rule
CREATE TABLE IF NOT EXISTS tax_charge_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tax_charge_rule_tenant ON tax_charge_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: reinsurance_cost_rule
CREATE TABLE IF NOT EXISTS reinsurance_cost_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_cost_rule_tenant ON reinsurance_cost_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: premium_calculation
CREATE TABLE IF NOT EXISTS premium_calculation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_premium_calculation_tenant ON premium_calculation(tenant_id);

-- DOMAIN: PRICING | TABLE: premium_component
CREATE TABLE IF NOT EXISTS premium_component (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  component_code VARCHAR(80) NOT NULL,
  calculation_order INT NOT NULL DEFAULT 0,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_premium_component_tenant ON premium_component(tenant_id);

-- DOMAIN: PRICING | TABLE: premium_adjustment
CREATE TABLE IF NOT EXISTS premium_adjustment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_premium_adjustment_tenant ON premium_adjustment(tenant_id);

-- DOMAIN: PRICING | TABLE: premium_floor_rule
CREATE TABLE IF NOT EXISTS premium_floor_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_premium_floor_rule_tenant ON premium_floor_rule(tenant_id);

-- DOMAIN: PRICING | TABLE: premium_floor_result
CREATE TABLE IF NOT EXISTS premium_floor_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_premium_floor_result_tenant ON premium_floor_result(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_explanation
CREATE TABLE IF NOT EXISTS pricing_explanation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_explanation_tenant ON pricing_explanation(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_explanation_item
CREATE TABLE IF NOT EXISTS pricing_explanation_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_explanation_item_tenant ON pricing_explanation_item(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_simulation
CREATE TABLE IF NOT EXISTS pricing_simulation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_simulation_tenant ON pricing_simulation(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_simulation_parameter
CREATE TABLE IF NOT EXISTS pricing_simulation_parameter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_simulation_parameter_tenant ON pricing_simulation_parameter(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_simulation_result
CREATE TABLE IF NOT EXISTS pricing_simulation_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_simulation_result_tenant ON pricing_simulation_result(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_scenario
CREATE TABLE IF NOT EXISTS pricing_scenario (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_scenario_tenant ON pricing_scenario(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_scenario_result
CREATE TABLE IF NOT EXISTS pricing_scenario_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_scenario_result_tenant ON pricing_scenario_result(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_leakage_metric
CREATE TABLE IF NOT EXISTS pricing_leakage_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_leakage_metric_tenant ON pricing_leakage_metric(tenant_id);

-- DOMAIN: PRICING | TABLE: technical_rate
CREATE TABLE IF NOT EXISTS technical_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_technical_rate_tenant ON technical_rate(tenant_id);

-- DOMAIN: PRICING | TABLE: commercial_rate
CREATE TABLE IF NOT EXISTS commercial_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_commercial_rate_tenant ON commercial_rate(tenant_id);

-- DOMAIN: PRICING | TABLE: member_rate
CREATE TABLE IF NOT EXISTS member_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_rate_tenant ON member_rate(tenant_id);

-- DOMAIN: PRICING | TABLE: family_rate
CREATE TABLE IF NOT EXISTS family_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_family_rate_tenant ON family_rate(tenant_id);

-- DOMAIN: PRICING | TABLE: group_rate
CREATE TABLE IF NOT EXISTS group_rate (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_group_rate_tenant ON group_rate(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_error
CREATE TABLE IF NOT EXISTS pricing_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_error_tenant ON pricing_error(tenant_id);

-- DOMAIN: PRICING | TABLE: pricing_audit
CREATE TABLE IF NOT EXISTS pricing_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_pricing_audit_tenant ON pricing_audit(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurer
CREATE TABLE IF NOT EXISTS reinsurer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurer_tenant ON reinsurer(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurer_contact
CREATE TABLE IF NOT EXISTS reinsurer_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurer_contact_tenant ON reinsurer_contact(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: treaty
CREATE TABLE IF NOT EXISTS treaty (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_treaty_tenant ON treaty(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: treaty_version
CREATE TABLE IF NOT EXISTS treaty_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_treaty_version_tenant ON treaty_version(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: treaty_section
CREATE TABLE IF NOT EXISTS treaty_section (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_treaty_section_tenant ON treaty_section(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_layer
CREATE TABLE IF NOT EXISTS reinsurance_layer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_layer_tenant ON reinsurance_layer(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: retention_rule
CREATE TABLE IF NOT EXISTS retention_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_retention_rule_tenant ON retention_rule(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: capacity_rule
CREATE TABLE IF NOT EXISTS capacity_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_capacity_rule_tenant ON capacity_rule(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_exclusion
CREATE TABLE IF NOT EXISTS reinsurance_exclusion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_exclusion_tenant ON reinsurance_exclusion(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_territory
CREATE TABLE IF NOT EXISTS reinsurance_territory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_territory_tenant ON reinsurance_territory(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_special_condition
CREATE TABLE IF NOT EXISTS reinsurance_special_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_special_condition_tenant ON reinsurance_special_condition(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_assessment
CREATE TABLE IF NOT EXISTS reinsurance_assessment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_assessment_tenant ON reinsurance_assessment(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_allocation
CREATE TABLE IF NOT EXISTS reinsurance_allocation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_allocation_tenant ON reinsurance_allocation(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_cession
CREATE TABLE IF NOT EXISTS reinsurance_cession (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_cession_tenant ON reinsurance_cession(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_premium
CREATE TABLE IF NOT EXISTS reinsurance_premium (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_premium_tenant ON reinsurance_premium(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: facultative_request
CREATE TABLE IF NOT EXISTS facultative_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_request_tenant ON facultative_request(tenant_id);
CREATE INDEX IF NOT EXISTS idx_facultative_request_status ON facultative_request(tenant_id, status);

-- DOMAIN: REINSURANCE | TABLE: facultative_request_risk
CREATE TABLE IF NOT EXISTS facultative_request_risk (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_request_risk_tenant ON facultative_request_risk(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: facultative_market
CREATE TABLE IF NOT EXISTS facultative_market (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_market_tenant ON facultative_market(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: facultative_offer
CREATE TABLE IF NOT EXISTS facultative_offer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_offer_tenant ON facultative_offer(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: facultative_offer_condition
CREATE TABLE IF NOT EXISTS facultative_offer_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_offer_condition_tenant ON facultative_offer_condition(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: facultative_placement
CREATE TABLE IF NOT EXISTS facultative_placement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_placement_tenant ON facultative_placement(tenant_id);
CREATE INDEX IF NOT EXISTS idx_facultative_placement_status ON facultative_placement(tenant_id, status);

-- DOMAIN: REINSURANCE | TABLE: facultative_status_history
CREATE TABLE IF NOT EXISTS facultative_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_facultative_status_history_tenant ON facultative_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_facultative_status_history_status ON facultative_status_history(tenant_id, status);

-- DOMAIN: REINSURANCE | TABLE: reinsurer_response
CREATE TABLE IF NOT EXISTS reinsurer_response (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurer_response_tenant ON reinsurer_response(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_document
CREATE TABLE IF NOT EXISTS reinsurance_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_document_tenant ON reinsurance_document(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_recovery
CREATE TABLE IF NOT EXISTS reinsurance_recovery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_recovery_tenant ON reinsurance_recovery(tenant_id);

-- DOMAIN: REINSURANCE | TABLE: reinsurance_accumulation
CREATE TABLE IF NOT EXISTS reinsurance_accumulation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_reinsurance_accumulation_tenant ON reinsurance_accumulation(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_case
CREATE TABLE IF NOT EXISTS underwriting_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  case_number VARCHAR(60) NOT NULL,
  case_type VARCHAR(30) NOT NULL,
  effective_date DATE NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_case_tenant ON underwriting_case(tenant_id);
CREATE INDEX IF NOT EXISTS idx_underwriting_case_status ON underwriting_case(tenant_id, status);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_case_party
CREATE TABLE IF NOT EXISTS underwriting_case_party (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_case_party_tenant ON underwriting_case_party(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_case_member
CREATE TABLE IF NOT EXISTS underwriting_case_member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_case_member_tenant ON underwriting_case_member(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_fact
CREATE TABLE IF NOT EXISTS underwriting_fact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_fact_tenant ON underwriting_fact(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_input_snapshot
CREATE TABLE IF NOT EXISTS underwriting_input_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_input_snapshot_tenant ON underwriting_input_snapshot(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_engine_result
CREATE TABLE IF NOT EXISTS underwriting_engine_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_engine_result_tenant ON underwriting_engine_result(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_alert
CREATE TABLE IF NOT EXISTS underwriting_alert (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_alert_tenant ON underwriting_alert(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_decision
CREATE TABLE IF NOT EXISTS underwriting_decision (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_decision_tenant ON underwriting_decision(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_decision_reason
CREATE TABLE IF NOT EXISTS underwriting_decision_reason (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_decision_reason_tenant ON underwriting_decision_reason(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_condition
CREATE TABLE IF NOT EXISTS underwriting_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_condition_tenant ON underwriting_condition(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_referral
CREATE TABLE IF NOT EXISTS underwriting_referral (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_referral_tenant ON underwriting_referral(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_assignment
CREATE TABLE IF NOT EXISTS underwriting_assignment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_assignment_tenant ON underwriting_assignment(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_note
CREATE TABLE IF NOT EXISTS underwriting_note (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_note_tenant ON underwriting_note(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_attachment
CREATE TABLE IF NOT EXISTS underwriting_attachment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_attachment_tenant ON underwriting_attachment(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_case_history
CREATE TABLE IF NOT EXISTS underwriting_case_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_case_history_tenant ON underwriting_case_history(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_sla
CREATE TABLE IF NOT EXISTS underwriting_sla (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_sla_tenant ON underwriting_sla(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_sla_event
CREATE TABLE IF NOT EXISTS underwriting_sla_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_sla_event_tenant ON underwriting_sla_event(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: approval_request
CREATE TABLE IF NOT EXISTS approval_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_approval_request_tenant ON approval_request(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: approval
CREATE TABLE IF NOT EXISTS approval (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_approval_tenant ON approval(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: approval_comment
CREATE TABLE IF NOT EXISTS approval_comment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_approval_comment_tenant ON approval_comment(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: authority_check
CREATE TABLE IF NOT EXISTS authority_check (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authority_check_tenant ON authority_check(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: decision_snapshot
CREATE TABLE IF NOT EXISTS decision_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_decision_snapshot_tenant ON decision_snapshot(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: decision_explanation
CREATE TABLE IF NOT EXISTS decision_explanation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_decision_explanation_tenant ON decision_explanation(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: decision_explanation_item
CREATE TABLE IF NOT EXISTS decision_explanation_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_decision_explanation_item_tenant ON decision_explanation_item(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_exception
CREATE TABLE IF NOT EXISTS underwriting_exception (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_exception_tenant ON underwriting_exception(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_override
CREATE TABLE IF NOT EXISTS underwriting_override (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_override_tenant ON underwriting_override(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: underwriting_watchlist
CREATE TABLE IF NOT EXISTS underwriting_watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_underwriting_watchlist_tenant ON underwriting_watchlist(tenant_id);

-- DOMAIN: UNDERWRITING | TABLE: watchlist_event
CREATE TABLE IF NOT EXISTS watchlist_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_watchlist_event_tenant ON watchlist_event(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_request
CREATE TABLE IF NOT EXISTS quote_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_request_tenant ON quote_request(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote
CREATE TABLE IF NOT EXISTS quote (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  quote_number VARCHAR(60) NOT NULL,
  valid_until DATE NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_tenant ON quote(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quote_status ON quote(tenant_id, status);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_version
CREATE TABLE IF NOT EXISTS quote_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_version_tenant ON quote_version(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_member
CREATE TABLE IF NOT EXISTS quote_member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_member_tenant ON quote_member(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_coverage
CREATE TABLE IF NOT EXISTS quote_coverage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_coverage_tenant ON quote_coverage(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_benefit
CREATE TABLE IF NOT EXISTS quote_benefit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_benefit_tenant ON quote_benefit(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_premium
CREATE TABLE IF NOT EXISTS quote_premium (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_premium_tenant ON quote_premium(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_premium_component
CREATE TABLE IF NOT EXISTS quote_premium_component (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_premium_component_tenant ON quote_premium_component(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_condition
CREATE TABLE IF NOT EXISTS quote_condition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_condition_tenant ON quote_condition(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_exclusion
CREATE TABLE IF NOT EXISTS quote_exclusion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_exclusion_tenant ON quote_exclusion(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_document
CREATE TABLE IF NOT EXISTS quote_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_document_tenant ON quote_document(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_status_history
CREATE TABLE IF NOT EXISTS quote_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_status_history_tenant ON quote_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quote_status_history_status ON quote_status_history(tenant_id, status);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_acceptance
CREATE TABLE IF NOT EXISTS quote_acceptance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_acceptance_tenant ON quote_acceptance(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_rejection
CREATE TABLE IF NOT EXISTS quote_rejection (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_rejection_tenant ON quote_rejection(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: quote_expiry
CREATE TABLE IF NOT EXISTS quote_expiry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_quote_expiry_tenant ON quote_expiry(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: binding
CREATE TABLE IF NOT EXISTS binding (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_binding_tenant ON binding(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy
CREATE TABLE IF NOT EXISTS policy (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  policy_number VARCHAR(60) NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_tenant ON policy(tenant_id);
CREATE INDEX IF NOT EXISTS idx_policy_status ON policy(tenant_id, status);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_version
CREATE TABLE IF NOT EXISTS policy_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_version_tenant ON policy_version(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_member
CREATE TABLE IF NOT EXISTS policy_member (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_member_tenant ON policy_member(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_coverage
CREATE TABLE IF NOT EXISTS policy_coverage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_coverage_tenant ON policy_coverage(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_benefit
CREATE TABLE IF NOT EXISTS policy_benefit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_benefit_tenant ON policy_benefit(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_premium
CREATE TABLE IF NOT EXISTS policy_premium (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_premium_tenant ON policy_premium(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_status_history
CREATE TABLE IF NOT EXISTS policy_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_status_history_tenant ON policy_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_policy_status_history_status ON policy_status_history(tenant_id, status);

-- DOMAIN: QUOTE_POLICY | TABLE: endorsement
CREATE TABLE IF NOT EXISTS endorsement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_endorsement_tenant ON endorsement(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: endorsement_version
CREATE TABLE IF NOT EXISTS endorsement_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_endorsement_version_tenant ON endorsement_version(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: endorsement_member_change
CREATE TABLE IF NOT EXISTS endorsement_member_change (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_endorsement_member_change_tenant ON endorsement_member_change(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: endorsement_coverage_change
CREATE TABLE IF NOT EXISTS endorsement_coverage_change (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_endorsement_coverage_change_tenant ON endorsement_coverage_change(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: endorsement_premium_adjustment
CREATE TABLE IF NOT EXISTS endorsement_premium_adjustment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_endorsement_premium_adjustment_tenant ON endorsement_premium_adjustment(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: prorata_calculation
CREATE TABLE IF NOT EXISTS prorata_calculation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_prorata_calculation_tenant ON prorata_calculation(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: refund_calculation
CREATE TABLE IF NOT EXISTS refund_calculation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_refund_calculation_tenant ON refund_calculation(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: additional_premium_calculation
CREATE TABLE IF NOT EXISTS additional_premium_calculation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_additional_premium_calculation_tenant ON additional_premium_calculation(tenant_id);

-- DOMAIN: QUOTE_POLICY | TABLE: policy_document
CREATE TABLE IF NOT EXISTS policy_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  policy_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_policy_document_tenant ON policy_document(tenant_id);

-- DOMAIN: TPA | TABLE: tpa
CREATE TABLE IF NOT EXISTS tpa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_tenant ON tpa(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_endpoint
CREATE TABLE IF NOT EXISTS tpa_endpoint (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_endpoint_tenant ON tpa_endpoint(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_credential_ref
CREATE TABLE IF NOT EXISTS tpa_credential_ref (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_credential_ref_tenant ON tpa_credential_ref(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_configuration
CREATE TABLE IF NOT EXISTS tpa_configuration (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_configuration_tenant ON tpa_configuration(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_mapping
CREATE TABLE IF NOT EXISTS tpa_mapping (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_mapping_tenant ON tpa_mapping(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_message_log
CREATE TABLE IF NOT EXISTS tpa_message_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_message_log_tenant ON tpa_message_log(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_member_sync
CREATE TABLE IF NOT EXISTS tpa_member_sync (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_member_sync_tenant ON tpa_member_sync(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_member_sync_error
CREATE TABLE IF NOT EXISTS tpa_member_sync_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_member_sync_error_tenant ON tpa_member_sync_error(tenant_id);

-- DOMAIN: TPA | TABLE: eligibility_check
CREATE TABLE IF NOT EXISTS eligibility_check (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_check_tenant ON eligibility_check(tenant_id);

-- DOMAIN: TPA | TABLE: eligibility_result
CREATE TABLE IF NOT EXISTS eligibility_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_result_tenant ON eligibility_result(tenant_id);

-- DOMAIN: TPA | TABLE: eligibility_reason
CREATE TABLE IF NOT EXISTS eligibility_reason (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_eligibility_reason_tenant ON eligibility_reason(tenant_id);

-- DOMAIN: TPA | TABLE: authorization
CREATE TABLE IF NOT EXISTS authorization (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_tenant ON authorization(tenant_id);
CREATE INDEX IF NOT EXISTS idx_authorization_status ON authorization(tenant_id, status);

-- DOMAIN: TPA | TABLE: authorization_line
CREATE TABLE IF NOT EXISTS authorization_line (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_line_tenant ON authorization_line(tenant_id);

-- DOMAIN: TPA | TABLE: authorization_status_history
CREATE TABLE IF NOT EXISTS authorization_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_status_history_tenant ON authorization_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_authorization_status_history_status ON authorization_status_history(tenant_id, status);

-- DOMAIN: TPA | TABLE: authorization_decision
CREATE TABLE IF NOT EXISTS authorization_decision (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_decision_tenant ON authorization_decision(tenant_id);

-- DOMAIN: TPA | TABLE: authorization_medical_review
CREATE TABLE IF NOT EXISTS authorization_medical_review (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_medical_review_tenant ON authorization_medical_review(tenant_id);

-- DOMAIN: TPA | TABLE: authorization_document
CREATE TABLE IF NOT EXISTS authorization_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_authorization_document_tenant ON authorization_document(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_claim_sync
CREATE TABLE IF NOT EXISTS tpa_claim_sync (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_claim_sync_tenant ON tpa_claim_sync(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_claim_sync_error
CREATE TABLE IF NOT EXISTS tpa_claim_sync_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_claim_sync_error_tenant ON tpa_claim_sync_error(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_provider_sync
CREATE TABLE IF NOT EXISTS tpa_provider_sync (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_provider_sync_tenant ON tpa_provider_sync(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_provider_sync_error
CREATE TABLE IF NOT EXISTS tpa_provider_sync_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_provider_sync_error_tenant ON tpa_provider_sync_error(tenant_id);

-- DOMAIN: TPA | TABLE: card_request
CREATE TABLE IF NOT EXISTS card_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_card_request_tenant ON card_request(tenant_id);

-- DOMAIN: TPA | TABLE: card_status_history
CREATE TABLE IF NOT EXISTS card_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_card_status_history_tenant ON card_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_card_status_history_status ON card_status_history(tenant_id, status);

-- DOMAIN: TPA | TABLE: tpa_webhook_event
CREATE TABLE IF NOT EXISTS tpa_webhook_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_webhook_event_tenant ON tpa_webhook_event(tenant_id);

-- DOMAIN: TPA | TABLE: tpa_webhook_processing
CREATE TABLE IF NOT EXISTS tpa_webhook_processing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_tpa_webhook_processing_tenant ON tpa_webhook_processing(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_rule
CREATE TABLE IF NOT EXISTS fwa_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_rule_tenant ON fwa_rule(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_rule_version
CREATE TABLE IF NOT EXISTS fwa_rule_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_rule_version_tenant ON fwa_rule_version(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_assessment
CREATE TABLE IF NOT EXISTS fwa_assessment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_assessment_tenant ON fwa_assessment(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_score
CREATE TABLE IF NOT EXISTS fwa_score (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_score_tenant ON fwa_score(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_alert
CREATE TABLE IF NOT EXISTS fwa_alert (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_alert_tenant ON fwa_alert(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_alert_action
CREATE TABLE IF NOT EXISTS fwa_alert_action (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_alert_action_tenant ON fwa_alert_action(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_claim_feature
CREATE TABLE IF NOT EXISTS fwa_claim_feature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_claim_feature_tenant ON fwa_claim_feature(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_member_feature
CREATE TABLE IF NOT EXISTS fwa_member_feature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_member_feature_tenant ON fwa_member_feature(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_provider_feature
CREATE TABLE IF NOT EXISTS fwa_provider_feature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_provider_feature_tenant ON fwa_provider_feature(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_portfolio_feature
CREATE TABLE IF NOT EXISTS fwa_portfolio_feature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_portfolio_feature_tenant ON fwa_portfolio_feature(tenant_id);

-- DOMAIN: FWA | TABLE: provider_anomaly
CREATE TABLE IF NOT EXISTS provider_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_provider_anomaly_tenant ON provider_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: member_anomaly
CREATE TABLE IF NOT EXISTS member_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  member_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_member_anomaly_tenant ON member_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: claim_anomaly
CREATE TABLE IF NOT EXISTS claim_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_claim_anomaly_tenant ON claim_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: duplicate_claim_signal
CREATE TABLE IF NOT EXISTS duplicate_claim_signal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_duplicate_claim_signal_tenant ON duplicate_claim_signal(tenant_id);

-- DOMAIN: FWA | TABLE: utilisation_anomaly
CREATE TABLE IF NOT EXISTS utilisation_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_utilisation_anomaly_tenant ON utilisation_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: coding_anomaly
CREATE TABLE IF NOT EXISTS coding_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_coding_anomaly_tenant ON coding_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: billing_anomaly
CREATE TABLE IF NOT EXISTS billing_anomaly (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_billing_anomaly_tenant ON billing_anomaly(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_case
CREATE TABLE IF NOT EXISTS fwa_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_case_tenant ON fwa_case(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_case_note
CREATE TABLE IF NOT EXISTS fwa_case_note (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_case_note_tenant ON fwa_case_note(tenant_id);

-- DOMAIN: FWA | TABLE: fwa_case_status_history
CREATE TABLE IF NOT EXISTS fwa_case_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_fwa_case_status_history_tenant ON fwa_case_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fwa_case_status_history_status ON fwa_case_status_history(tenant_id, status);

-- DOMAIN: RENEWAL | TABLE: renewal_case
CREATE TABLE IF NOT EXISTS renewal_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_case_tenant ON renewal_case(tenant_id);
CREATE INDEX IF NOT EXISTS idx_renewal_case_status ON renewal_case(tenant_id, status);

-- DOMAIN: RENEWAL | TABLE: renewal_window
CREATE TABLE IF NOT EXISTS renewal_window (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_window_tenant ON renewal_window(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_snapshot
CREATE TABLE IF NOT EXISTS renewal_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_snapshot_tenant ON renewal_snapshot(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_population_snapshot
CREATE TABLE IF NOT EXISTS renewal_population_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_population_snapshot_tenant ON renewal_population_snapshot(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_claims_snapshot
CREATE TABLE IF NOT EXISTS renewal_claims_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_claims_snapshot_tenant ON renewal_claims_snapshot(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_pricing_result
CREATE TABLE IF NOT EXISTS renewal_pricing_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_pricing_result_tenant ON renewal_pricing_result(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_risk_change
CREATE TABLE IF NOT EXISTS renewal_risk_change (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_risk_change_tenant ON renewal_risk_change(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_recommendation
CREATE TABLE IF NOT EXISTS renewal_recommendation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_recommendation_tenant ON renewal_recommendation(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_recommendation_reason
CREATE TABLE IF NOT EXISTS renewal_recommendation_reason (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_recommendation_reason_tenant ON renewal_recommendation_reason(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_quote_link
CREATE TABLE IF NOT EXISTS renewal_quote_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  quote_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_quote_link_tenant ON renewal_quote_link(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_status_history
CREATE TABLE IF NOT EXISTS renewal_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_status_history_tenant ON renewal_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_renewal_status_history_status ON renewal_status_history(tenant_id, status);

-- DOMAIN: RENEWAL | TABLE: renewal_watchlist
CREATE TABLE IF NOT EXISTS renewal_watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_watchlist_tenant ON renewal_watchlist(tenant_id);

-- DOMAIN: RENEWAL | TABLE: renewal_watchlist_event
CREATE TABLE IF NOT EXISTS renewal_watchlist_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_renewal_watchlist_event_tenant ON renewal_watchlist_event(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: regulatory_jurisdiction
CREATE TABLE IF NOT EXISTS regulatory_jurisdiction (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_regulatory_jurisdiction_tenant ON regulatory_jurisdiction(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: regulatory_source
CREATE TABLE IF NOT EXISTS regulatory_source (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_regulatory_source_tenant ON regulatory_source(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: regulatory_rule_set
CREATE TABLE IF NOT EXISTS regulatory_rule_set (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_regulatory_rule_set_tenant ON regulatory_rule_set(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: regulatory_rule
CREATE TABLE IF NOT EXISTS regulatory_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_regulatory_rule_tenant ON regulatory_rule(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: regulatory_rule_version
CREATE TABLE IF NOT EXISTS regulatory_rule_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_regulatory_rule_version_tenant ON regulatory_rule_version(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: compliance_assessment
CREATE TABLE IF NOT EXISTS compliance_assessment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_compliance_assessment_tenant ON compliance_assessment(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: compliance_result
CREATE TABLE IF NOT EXISTS compliance_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_compliance_result_tenant ON compliance_result(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: compliance_violation
CREATE TABLE IF NOT EXISTS compliance_violation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_compliance_violation_tenant ON compliance_violation(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: compliance_exception
CREATE TABLE IF NOT EXISTS compliance_exception (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_compliance_exception_tenant ON compliance_exception(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: compliance_approval
CREATE TABLE IF NOT EXISTS compliance_approval (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_compliance_approval_tenant ON compliance_approval(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: data_retention_rule
CREATE TABLE IF NOT EXISTS data_retention_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_data_retention_rule_tenant ON data_retention_rule(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: privacy_purpose
CREATE TABLE IF NOT EXISTS privacy_purpose (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_privacy_purpose_tenant ON privacy_purpose(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: consent_template
CREATE TABLE IF NOT EXISTS consent_template (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_consent_template_tenant ON consent_template(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: consent_template_version
CREATE TABLE IF NOT EXISTS consent_template_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_consent_template_version_tenant ON consent_template_version(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: data_subject_request
CREATE TABLE IF NOT EXISTS data_subject_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_data_subject_request_tenant ON data_subject_request(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: data_access_request
CREATE TABLE IF NOT EXISTS data_access_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_data_access_request_tenant ON data_access_request(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: break_glass_request
CREATE TABLE IF NOT EXISTS break_glass_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_break_glass_request_tenant ON break_glass_request(tenant_id);

-- DOMAIN: COMPLIANCE | TABLE: break_glass_access
CREATE TABLE IF NOT EXISTS break_glass_access (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_break_glass_access_tenant ON break_glass_access(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_template
CREATE TABLE IF NOT EXISTS document_template (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_template_tenant ON document_template(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_template_version
CREATE TABLE IF NOT EXISTS document_template_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_template_version_tenant ON document_template_version(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: generated_document
CREATE TABLE IF NOT EXISTS generated_document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_generated_document_tenant ON generated_document(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_generation_request
CREATE TABLE IF NOT EXISTS document_generation_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_generation_request_tenant ON document_generation_request(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_merge_field
CREATE TABLE IF NOT EXISTS document_merge_field (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_merge_field_tenant ON document_merge_field(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_signature_request
CREATE TABLE IF NOT EXISTS document_signature_request (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_signature_request_tenant ON document_signature_request(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_signature
CREATE TABLE IF NOT EXISTS document_signature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_signature_tenant ON document_signature(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_delivery
CREATE TABLE IF NOT EXISTS document_delivery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_delivery_tenant ON document_delivery(tenant_id);

-- DOMAIN: DOCUMENT | TABLE: document_archive_ref
CREATE TABLE IF NOT EXISTS document_archive_ref (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_document_archive_ref_tenant ON document_archive_ref(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification_template
CREATE TABLE IF NOT EXISTS notification_template (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_template_tenant ON notification_template(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification_template_version
CREATE TABLE IF NOT EXISTS notification_template_version (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  effective_from DATE ,
  effective_to DATE ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_template_version_tenant ON notification_template_version(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification
CREATE TABLE IF NOT EXISTS notification (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_tenant ON notification(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification_recipient
CREATE TABLE IF NOT EXISTS notification_recipient (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_recipient_tenant ON notification_recipient(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification_delivery
CREATE TABLE IF NOT EXISTS notification_delivery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_delivery_tenant ON notification_delivery(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: notification_preference
CREATE TABLE IF NOT EXISTS notification_preference (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_notification_preference_tenant ON notification_preference(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: webhook_subscription
CREATE TABLE IF NOT EXISTS webhook_subscription (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_webhook_subscription_tenant ON webhook_subscription(tenant_id);

-- DOMAIN: NOTIFICATION | TABLE: webhook_delivery
CREATE TABLE IF NOT EXISTS webhook_delivery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_tenant ON webhook_delivery(tenant_id);

-- DOMAIN: REPORTING | TABLE: report_definition
CREATE TABLE IF NOT EXISTS report_definition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_report_definition_tenant ON report_definition(tenant_id);

-- DOMAIN: REPORTING | TABLE: report_parameter
CREATE TABLE IF NOT EXISTS report_parameter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_report_parameter_tenant ON report_parameter(tenant_id);

-- DOMAIN: REPORTING | TABLE: report_execution
CREATE TABLE IF NOT EXISTS report_execution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_report_execution_tenant ON report_execution(tenant_id);

-- DOMAIN: REPORTING | TABLE: report_output
CREATE TABLE IF NOT EXISTS report_output (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_report_output_tenant ON report_output(tenant_id);

-- DOMAIN: REPORTING | TABLE: dashboard_definition
CREATE TABLE IF NOT EXISTS dashboard_definition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dashboard_definition_tenant ON dashboard_definition(tenant_id);

-- DOMAIN: REPORTING | TABLE: dashboard_widget
CREATE TABLE IF NOT EXISTS dashboard_widget (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dashboard_widget_tenant ON dashboard_widget(tenant_id);

-- DOMAIN: REPORTING | TABLE: dashboard_user_preference
CREATE TABLE IF NOT EXISTS dashboard_user_preference (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dashboard_user_preference_tenant ON dashboard_user_preference(tenant_id);

-- DOMAIN: REPORTING | TABLE: read_model_underwriting_case
CREATE TABLE IF NOT EXISTS read_model_underwriting_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  underwriting_case_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_read_model_underwriting_case_tenant ON read_model_underwriting_case(tenant_id);

-- DOMAIN: REPORTING | TABLE: read_model_portfolio_metric
CREATE TABLE IF NOT EXISTS read_model_portfolio_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_read_model_portfolio_metric_tenant ON read_model_portfolio_metric(tenant_id);

-- DOMAIN: REPORTING | TABLE: read_model_renewal_metric
CREATE TABLE IF NOT EXISTS read_model_renewal_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_read_model_renewal_metric_tenant ON read_model_renewal_metric(tenant_id);

-- DOMAIN: REPORTING | TABLE: read_model_provider_metric
CREATE TABLE IF NOT EXISTS read_model_provider_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  code VARCHAR(80) ,
  name VARCHAR(240) ,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  provider_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_read_model_provider_metric_tenant ON read_model_provider_metric(tenant_id);

-- DOMAIN: REPORTING | TABLE: read_model_claim_metric
CREATE TABLE IF NOT EXISTS read_model_claim_metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  claim_id UUID ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_read_model_claim_metric_tenant ON read_model_claim_metric(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_system
CREATE TABLE IF NOT EXISTS integration_system (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_system_tenant ON integration_system(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_endpoint
CREATE TABLE IF NOT EXISTS integration_endpoint (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_endpoint_tenant ON integration_endpoint(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_credential_ref
CREATE TABLE IF NOT EXISTS integration_credential_ref (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_credential_ref_tenant ON integration_credential_ref(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_mapping
CREATE TABLE IF NOT EXISTS integration_mapping (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_mapping_tenant ON integration_mapping(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_message
CREATE TABLE IF NOT EXISTS integration_message (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_message_tenant ON integration_message(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_error
CREATE TABLE IF NOT EXISTS integration_error (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_error_tenant ON integration_error(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: integration_retry
CREATE TABLE IF NOT EXISTS integration_retry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_integration_retry_tenant ON integration_retry(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: outbox_event
CREATE TABLE IF NOT EXISTS outbox_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_outbox_event_tenant ON outbox_event(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: processed_event
CREATE TABLE IF NOT EXISTS processed_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_processed_event_tenant ON processed_event(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: dead_letter_event
CREATE TABLE IF NOT EXISTS dead_letter_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_dead_letter_event_tenant ON dead_letter_event(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: idempotency_record
CREATE TABLE IF NOT EXISTS idempotency_record (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_idempotency_record_tenant ON idempotency_record(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: api_request_log
CREATE TABLE IF NOT EXISTS api_request_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_api_request_log_tenant ON api_request_log(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: api_rate_limit_counter
CREATE TABLE IF NOT EXISTS api_rate_limit_counter (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  amount NUMERIC(20,2) ,
  currency CHAR(3) ,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_api_rate_limit_counter_tenant ON api_rate_limit_counter(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: external_reference
CREATE TABLE IF NOT EXISTS external_reference (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_external_reference_tenant ON external_reference(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: file_transfer_batch
CREATE TABLE IF NOT EXISTS file_transfer_batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_file_transfer_batch_tenant ON file_transfer_batch(tenant_id);

-- DOMAIN: INTEGRATION | TABLE: file_transfer_item
CREATE TABLE IF NOT EXISTS file_transfer_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_file_transfer_item_tenant ON file_transfer_item(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: audit_log
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: business_event
CREATE TABLE IF NOT EXISTS business_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_business_event_tenant ON business_event(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: business_event_payload
CREATE TABLE IF NOT EXISTS business_event_payload (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_business_event_payload_tenant ON business_event_payload(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: data_change_log
CREATE TABLE IF NOT EXISTS data_change_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_data_change_log_tenant ON data_change_log(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: security_event
CREATE TABLE IF NOT EXISTS security_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_security_event_tenant ON security_event(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: access_log
CREATE TABLE IF NOT EXISTS access_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_access_log_tenant ON access_log(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: job_definition
CREATE TABLE IF NOT EXISTS job_definition (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_job_definition_tenant ON job_definition(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: job_execution
CREATE TABLE IF NOT EXISTS job_execution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_job_execution_tenant ON job_execution(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: job_execution_step
CREATE TABLE IF NOT EXISTS job_execution_step (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_job_execution_step_tenant ON job_execution_step(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: scheduler_lock
CREATE TABLE IF NOT EXISTS scheduler_lock (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_scheduler_lock_tenant ON scheduler_lock(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: operational_alert
CREATE TABLE IF NOT EXISTS operational_alert (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_operational_alert_tenant ON operational_alert(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: operational_alert_event
CREATE TABLE IF NOT EXISTS operational_alert_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  correlation_id UUID ,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_operational_alert_event_tenant ON operational_alert_event(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: support_case
CREATE TABLE IF NOT EXISTS support_case (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_support_case_tenant ON support_case(tenant_id);

-- DOMAIN: AUDIT_OPS | TABLE: support_case_note
CREATE TABLE IF NOT EXISTS support_case_note (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID ,
  updated_at TIMESTAMPTZ ,
  updated_by UUID
);
CREATE INDEX IF NOT EXISTS idx_support_case_note_tenant ON support_case_note(tenant_id);
