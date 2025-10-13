// ================================================================
// TRANSLATION SOFTWARE DATABASE SCHEMA
// Standalone schema file for API endpoint generation
// ================================================================

const translationSchema = {

  // ================================================================
  // DATABASE INFORMATION
  // ================================================================

  database: {
    name: "translation",
    type: "mongodb",
    version: "1.0.0",
    description: "Translation software back office database for managing customers, subscriptions, payments, and translation transactions"
  },

  // ================================================================
  // COLLECTIONS/TABLES SCHEMA
  // ================================================================

  collections: {

    // ============================================================
    // CORE COLLECTIONS
    // ============================================================

    company: {
      description: "Company/customer information",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_id: { type: "String" },
        company_name: { type: "String", required: true },
        description: { type: "String" },
        address: {
          type: "Object",
          properties: {
            address0: { type: "String" },
            address1: { type: "String" },
            postal_code: { type: "String" },
            state: { type: "String" },
            city: { type: "String" },
            country: { type: "String" }
          }
        },
        contact_person: {
          type: "Object",
          properties: {
            name: { type: "String" },
            type: { type: "String" }
          }
        },
        phone_number: { type: "Array", items: { type: "String" } },
        company_url: { type: "Array", items: { type: "String" } },
        line_of_business: { type: "String" },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { company_name: 1 } },
        { fields: { line_of_business: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/companies",
        get: "GET /api/companies/:id",
        create: "POST /api/companies",
        update: "PUT /api/companies/:id",
        delete: "DELETE /api/companies/:id"
      }
    },

    company_users: {
      description: "Authorized users per company with role-based access",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        user_id: { type: "String", required: true, unique: true, maxLength: 255 },
        company_id: { type: "ObjectId", required: true, ref: "company" },
        user_name: { type: "String", required: true, maxLength: 255 },
        email: { type: "String", required: true, pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$" },
        phone_number: { type: "String", maxLength: 50 },
        permission_level: { type: "String", enum: ["admin", "user"], default: "user" },
        status: { type: "String", enum: ["active", "inactive", "suspended"], default: "active" },
        password_hash: { type: "String", sensitive: true },
        last_login: { type: "Date" },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { user_id: 1 }, unique: true },
        { fields: { company_id: 1 } },
        { fields: { email: 1 } },
        { fields: { company_id: 1, email: 1 }, unique: true }
      ],
      apiEndpoints: {
        list: "GET /api/companies/:companyId/users",
        get: "GET /api/users/:id",
        create: "POST /api/companies/:companyId/users",
        update: "PUT /api/users/:id",
        delete: "DELETE /api/users/:id"
      }
    },

    // ============================================================
    // SUBSCRIPTION & BILLING COLLECTIONS
    // ============================================================

    subscriptions: {
      description: "Customer subscription plans with usage tracking",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_id: { type: "ObjectId", required: true, ref: "company" },
        subscription_unit: { type: "String", required: true, enum: ["page", "word", "character"] },
        units_per_subscription: { type: "Integer", required: true },
        price_per_unit: { type: "Decimal", required: true },
        promotional_units: { type: "Integer", default: 0 },
        discount: { type: "Decimal", default: 1.0 },
        subscription_price: { type: "Decimal", required: true },
        start_date: { type: "Date", required: true },
        end_date: { type: "Date" },
        status: { type: "String", enum: ["active", "inactive", "expired"], default: "active" },
        usage_periods: {
          type: "Array",
          items: {
            type: "Object",
            properties: {
              period_start: { type: "Date", required: true },
              period_end: { type: "Date", required: true },
              units_allocated: { type: "Integer", required: true },
              units_used: { type: "Integer", default: 0 },
              units_remaining: { type: "Integer", required: true },
              promotional_units_used: { type: "Integer", default: 0 },
              last_updated: { type: "Date", default: "now" }
            }
          }
        },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { company_id: 1 } },
        { fields: { company_id: 1, status: 1 } },
        { fields: { status: 1 } }
      ],
      businessLogic: {
        onTransactionCreate: "Decrement units_remaining in current usage_period",
        onPeriodEnd: "Create new usage_period if subscription is active",
        onStatusChange: "Add entry to history array"
      },
      apiEndpoints: {
        list: "GET /api/companies/:companyId/subscriptions",
        get: "GET /api/subscriptions/:id",
        create: "POST /api/companies/:companyId/subscriptions",
        update: "PUT /api/subscriptions/:id",
        cancel: "POST /api/subscriptions/:id/cancel"
      }
    },

    invoices: {
      description: "Customer invoices for billing",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_id: { type: "ObjectId", required: true, ref: "company" },
        subscription_id: { type: "ObjectId", ref: "subscriptions" },
        invoice_number: { type: "String", required: true, unique: true, maxLength: 50 },
        invoice_date: { type: "Date", required: true },
        due_date: { type: "Date", required: true },
        total_amount: { type: "Decimal", required: true },
        tax_amount: { type: "Decimal", default: 0 },
        status: { type: "String", enum: ["draft", "sent", "paid", "overdue", "cancelled"], default: "pending" },
        pdf_url: { type: "String" },
        payment_applications: {
          type: "Array",
          items: {
            type: "Object",
            properties: {
              payment_id: { type: "ObjectId", ref: "payments" },
              amount_applied: { type: "Decimal", required: true },
              applied_date: { type: "Date", default: "now" }
            }
          }
        },
        created_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { invoice_number: 1 }, unique: true },
        { fields: { company_id: 1 } },
        { fields: { status: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/companies/:companyId/invoices",
        get: "GET /api/invoices/:id",
        create: "POST /api/companies/:companyId/invoices",
        update: "PUT /api/invoices/:id"
      }
    },

    payments: {
      description: "Square payment transactions",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_id: { type: "ObjectId", required: true, ref: "company" },
        subscription_id: { type: "ObjectId", ref: "subscriptions" },
        square_payment_id: { type: "String", required: true, unique: true, maxLength: 255 },
        square_order_id: { type: "String" },
        square_receipt_url: { type: "String" },
        amount: { type: "Decimal", required: true },
        currency: { type: "String", default: "USD", maxLength: 3 },
        payment_status: { type: "String", required: true, enum: ["completed", "pending", "failed", "refunded", "partially_refunded"] },
        payment_method: { type: "String" },
        card_brand: { type: "String" },
        last_4_digits: { type: "String", maxLength: 4 },
        processing_fee: { type: "Decimal" },
        net_amount: { type: "Decimal" },
        refunded_amount: { type: "Decimal", default: 0 },
        payment_date: { type: "Date", required: true },
        notes: { type: "String" },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { square_payment_id: 1 }, unique: true },
        { fields: { company_id: 1 } },
        { fields: { payment_date: -1 } }
      ],
      apiEndpoints: {
        list: "GET /api/companies/:companyId/payments",
        get: "GET /api/payments/:id",
        create: "POST /api/payments",
        webhook: "POST /api/payments/webhook"
      }
    },

    // ============================================================
    // TRANSLATION OPERATIONS
    // ============================================================

    translation_transactions: {
      description: "Translation job transactions with file metadata",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_id: { type: "ObjectId", required: true, ref: "company" },
        subscription_id: { type: "ObjectId", ref: "subscriptions" },
        requester_id: { type: "String", required: true },
        user_name: { type: "String", required: true },
        transaction_date: { type: "Date", required: true, default: "now" },
        units_consumed: { type: "Integer", required: true },
        original_file_url: { type: "String", required: true },
        translated_file_url: { type: "String" },
        source_language: { type: "String", required: true, maxLength: 10 },
        target_language: { type: "String", required: true, maxLength: 10 },
        status: { type: "String", enum: ["pending", "completed", "failed"], default: "completed" },
        error_message: { type: "String" },
        file_metadata: {
          type: "Object",
          properties: {
            file_name: { type: "String" },
            file_size_bytes: { type: "Long" },
            file_format: { type: "String" },
            page_count: { type: "Integer" },
            word_count: { type: "Integer" },
            character_count: { type: "Integer" }
          }
        },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { company_id: 1 } },
        { fields: { subscription_id: 1 } },
        { fields: { transaction_date: -1 } },
        { fields: { status: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/companies/:companyId/transactions",
        get: "GET /api/transactions/:id",
        create: "POST /api/transactions",
        update: "PUT /api/transactions/:id"
      }
    }
  },

  // ================================================================
  // BUSINESS RULES & VALIDATIONS
  // ================================================================

  businessRules: {
    subscriptions: {
      mustHaveActiveSubscription: "User must have active subscription to create translation",
      checkUnitsAvailable: "Verify units_remaining >= units_consumed before transaction",
      autoRenewal: "Check for auto_renewal flag and create new period on end_date",
      promotionalUnitsFirst: "Use promotional_units before regular units"
    },

    payments: {
      webhookVerification: "Verify Square webhook signature before processing",
      idempotency: "Use square_payment_id for idempotency to prevent duplicate processing",
      reconciliation: "Match payments to invoices via payment_applications"
    },

    permissions: {
      adminOnly: "Only 'admin' permission_level can manage users and subscriptions",
      customerIsolation: "Users can only access data for their company_id",
      systemAdminAccess: "system_admins have access to all customer data"
    },

    audit: {
      logAllChanges: "Log all CREATE, UPDATE, DELETE operations to audit_logs",
      sensitiveFields: "Don't log password_hash or key_hash in audit logs",
      retention: "Keep audit logs for 7 years for compliance"
    }
  }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = translationSchema;
}


