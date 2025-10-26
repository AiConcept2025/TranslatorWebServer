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
    type: "mongodb", // Can also be "postgresql"
    version: "1.0.0",
    description: "Translation software back office database for managing customers, subscriptions, payments, and translation transactions"
  },

  // ================================================================
  // COLLECTIONS/TABLES SCHEMA
  // ================================================================

  collections: {

    // ============================================================
    // ADMIN/SYSTEM COLLECTIONS
    // ============================================================

    system_config: {
      description: "System-wide configuration settings",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        config_key: { type: "String", required: true, unique: true, maxLength: 100 },
        config_value: { type: "String", required: true },
        config_type: { type: "String", enum: ["string", "integer", "boolean", "json"], default: "string" },
        description: { type: "String" },
        is_sensitive: { type: "Boolean", default: false },
        updated_by: { type: "String" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { config_key: 1 }, unique: true }
      ],
      apiEndpoints: {
        list: "GET /api/config",
        get: "GET /api/config/:key",
        update: "PUT /api/config/:key",
        create: "POST /api/config"
      }
    },

    schema_versions: {
      description: "Database schema version tracking for migrations",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        version_number: { type: "String", required: true },
        description: { type: "String" },
        applied_at: { type: "Date", required: true, default: "now" },
        applied_by: { type: "String" }
      },
      indexes: [
        { fields: { version_number: 1 } },
        { fields: { applied_at: -1 } }
      ],
      apiEndpoints: {
        list: "GET /api/schema-versions",
        get: "GET /api/schema-versions/:id"
      }
    },

    system_admins: {
      description: "System administrators who manage the platform",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        username: { type: "String", required: true, unique: true, maxLength: 100 },
        email: { type: "String", required: true, unique: true, pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$" },
        password_hash: { type: "String", required: true, sensitive: true },
        full_name: { type: "String" },
        role: { type: "String", enum: ["super_admin", "admin", "support"], default: "admin" },
        status: { type: "String", enum: ["active", "inactive", "suspended"], default: "active" },
        last_login: { type: "Date" },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { username: 1 }, unique: true },
        { fields: { email: 1 }, unique: true },
        { fields: { status: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/admins",
        get: "GET /api/admins/:id",
        create: "POST /api/admins",
        update: "PUT /api/admins/:id",
        delete: "DELETE /api/admins/:id",
        login: "POST /api/admins/login"
      }
    },

    system_activity_log: {
      description: "Activity log for system administrators",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        admin_id: { type: "ObjectId", ref: "system_admins" },
        activity_type: { type: "String", required: true },
        description: { type: "String" },
        ip_address: { type: "String" },
        user_agent: { type: "String" },
        created_at: { type: "Date", required: true, default: "now" }
      },
      indexes: [
        { fields: { admin_id: 1 } },
        { fields: { created_at: -1 } },
        { fields: { activity_type: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/activity-logs",
        get: "GET /api/activity-logs/:id",
        create: "POST /api/activity-logs"
      }
    },

    // ============================================================
    // CORE COLLECTIONS
    // ============================================================

    customers: {
      description: "Company/customer information",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        company_name: { type: "String", required: true, maxLength: 255 },
        address: { type: "String" },
        contact_person: { type: "String" },
        phone_number: { type: "String", maxLength: 50 },
        company_url: { type: "String", maxLength: 500 },
        line_of_business: { type: "String", maxLength: 255 },
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { company_name: 1 } },
        { fields: { line_of_business: 1 } },
        { fields: { company_name: "text" } }
      ],
      relationships: {
        hasMany: ["company_users", "subscriptions", "payments", "translation_transactions"]
      },
      apiEndpoints: {
        list: "GET /api/customers",
        get: "GET /api/customers/:id",
        create: "POST /api/customers",
        update: "PUT /api/customers/:id",
        delete: "DELETE /api/customers/:id",
        search: "GET /api/customers/search?q=:query"
      }
    },

    company_users: {
      description: "Authorized users per company with role-based access",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        user_id: { type: "String", required: true, unique: true, maxLength: 255 },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
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
        { fields: { customer_id: 1 } },
        { fields: { email: 1 } },
        { fields: { customer_id: 1, email: 1 }, unique: true },
        { fields: { customer_id: 1, permission_level: 1 } }
      ],
      relationships: {
        belongsTo: { collection: "customers", foreignKey: "customer_id" }
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/users",
        get: "GET /api/users/:id",
        create: "POST /api/customers/:customerId/users",
        update: "PUT /api/users/:id",
        delete: "DELETE /api/users/:id",
        login: "POST /api/users/login",
        changePassword: "POST /api/users/:id/change-password"
      }
    },

    // ============================================================
    // SUBSCRIPTION & BILLING COLLECTIONS
    // ============================================================

    subscriptions: {
      description: "Customer subscription plans with usage tracking",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
        subscription_unit: { type: "String", required: true, enum: ["page", "word", "character"] },
        units_per_subscription: { type: "Integer", required: true },
        price_per_unit: { type: "Decimal", required: true },
        promotional_units: { type: "Integer", default: 0 },
        subscription_price: { type: "Decimal", required: true },
        start_date: { type: "Date", required: true },
        end_date: { type: "Date" },
        status: { type: "String", enum: ["active", "inactive", "expired"], default: "active" },
        
        // Embedded usage periods
        usage_periods: {
          type: "Array",
          items: {
            period_start: { type: "Date", required: true },
            period_end: { type: "Date", required: true },
            units_allocated: { type: "Integer", required: true },
            units_used: { type: "Integer", default: 0 },
            units_remaining: { type: "Integer", required: true },
            promotional_units_used: { type: "Integer", default: 0 },
            last_updated: { type: "Date", default: "now" }
          }
        },
        
        // Embedded history
        history: {
          type: "Array",
          items: {
            change_type: { type: "String" },
            old_values: { type: "Object" },
            new_values: { type: "Object" },
            changed_by: { type: "String" },
            change_date: { type: "Date" }
          }
        },
        
        created_at: { type: "Date", default: "now" },
        updated_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { customer_id: 1 } },
        { fields: { customer_id: 1, status: 1 } },
        { fields: { start_date: 1 } },
        { fields: { end_date: 1 } },
        { fields: { status: 1 } }
      ],
      relationships: {
        belongsTo: { collection: "customers", foreignKey: "customer_id" },
        hasMany: ["translation_transactions", "payments"]
      },
      businessLogic: {
        onTransactionCreate: "Decrement units_remaining in current usage_period",
        onPeriodEnd: "Create new usage_period if subscription is active",
        onStatusChange: "Add entry to history array"
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/subscriptions",
        get: "GET /api/subscriptions/:id",
        create: "POST /api/customers/:customerId/subscriptions",
        update: "PUT /api/subscriptions/:id",
        cancel: "POST /api/subscriptions/:id/cancel",
        renew: "POST /api/subscriptions/:id/renew",
        usage: "GET /api/subscriptions/:id/usage"
      }
    },

    invoices: {
      description: "Customer invoices for billing",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
        subscription_id: { type: "ObjectId", ref: "subscriptions" },
        invoice_number: { type: "String", required: true, unique: true, maxLength: 50 },
        invoice_date: { type: "Date", required: true },
        due_date: { type: "Date", required: true },
        total_amount: { type: "Decimal", required: true },
        tax_amount: { type: "Decimal", default: 0 },
        status: { type: "String", enum: ["draft", "sent", "paid", "overdue", "cancelled"], default: "pending" },
        pdf_url: { type: "String" },
        
        // Embedded payment applications
        payment_applications: {
          type: "Array",
          items: {
            payment_id: { type: "ObjectId", ref: "payments" },
            amount_applied: { type: "Decimal", required: true },
            applied_date: { type: "Date", default: "now" }
          }
        },
        
        created_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { invoice_number: 1 }, unique: true },
        { fields: { customer_id: 1 } },
        { fields: { status: 1 } },
        { fields: { invoice_date: -1 } },
        { fields: { due_date: 1 } }
      ],
      relationships: {
        belongsTo: [
          { collection: "customers", foreignKey: "customer_id" },
          { collection: "subscriptions", foreignKey: "subscription_id" }
        ]
      },
      businessLogic: {
        onPaymentReceived: "Add to payment_applications array and update status",
        onDueDatePassed: "Change status to 'overdue' if not paid"
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/invoices",
        get: "GET /api/invoices/:id",
        create: "POST /api/customers/:customerId/invoices",
        update: "PUT /api/invoices/:id",
        send: "POST /api/invoices/:id/send",
        markPaid: "POST /api/invoices/:id/mark-paid",
        pdf: "GET /api/invoices/:id/pdf"
      }
    },

    payments: {
      description: "Square payment transactions",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
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
        { fields: { customer_id: 1 } },
        { fields: { subscription_id: 1 } },
        { fields: { payment_date: -1 } },
        { fields: { payment_status: 1 } }
      ],
      relationships: {
        belongsTo: [
          { collection: "customers", foreignKey: "customer_id" },
          { collection: "subscriptions", foreignKey: "subscription_id" }
        ]
      },
      businessLogic: {
        onPaymentCompleted: "Update invoice status and subscription",
        onRefund: "Update payment_status and refunded_amount"
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/payments",
        get: "GET /api/payments/:id",
        create: "POST /api/payments",
        webhook: "POST /api/payments/webhook",
        refund: "POST /api/payments/:id/refund"
      }
    },

    // ============================================================
    // TRANSLATION OPERATIONS
    // ============================================================

    translation_transactions: {
      description: "Translation job transactions with file metadata",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
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
        
        // Embedded file metadata
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
        { fields: { customer_id: 1 } },
        { fields: { subscription_id: 1 } },
        { fields: { transaction_date: -1 } },
        { fields: { customer_id: 1, requester_id: 1 } },
        { fields: { status: 1 } },
        { fields: { source_language: 1, target_language: 1 } }
      ],
      relationships: {
        belongsTo: [
          { collection: "customers", foreignKey: "customer_id" },
          { collection: "subscriptions", foreignKey: "subscription_id" }
        ]
      },
      businessLogic: {
        onTransactionCreate: "Decrement subscription usage, validate units available",
        onTransactionComplete: "Update translated_file_url and status",
        onTransactionFail: "Refund units to subscription, log error"
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/transactions",
        get: "GET /api/transactions/:id",
        create: "POST /api/transactions",
        update: "PUT /api/transactions/:id",
        retry: "POST /api/transactions/:id/retry",
        report: "GET /api/transactions/report"
      }
    },

    // ============================================================
    // SYSTEM & AUDIT
    // ============================================================

    audit_logs: {
      description: "Audit trail for all system changes",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        user_id: { type: "String", ref: "company_users.user_id" },
        customer_id: { type: "ObjectId", ref: "customers" },
        action: { type: "String", required: true },
        collection_name: { type: "String" },
        record_id: { type: "String" },
        old_values: { type: "Object" },
        new_values: { type: "Object" },
        ip_address: { type: "String" },
        timestamp: { type: "Date", required: true, default: "now" }
      },
      indexes: [
        { fields: { user_id: 1 } },
        { fields: { customer_id: 1 } },
        { fields: { timestamp: -1 } },
        { fields: { collection_name: 1, record_id: 1 } },
        { fields: { action: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/audit-logs",
        get: "GET /api/audit-logs/:id",
        search: "GET /api/audit-logs/search"
      }
    },

    notification_logs: {
      description: "Log of all notifications sent to users",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", ref: "customers" },
        user_id: { type: "String", ref: "company_users.user_id" },
        notification_type: { type: "String", required: true },
        subject: { type: "String" },
        status: { type: "String" },
        sent_at: { type: "Date", required: true, default: "now" }
      },
      indexes: [
        { fields: { customer_id: 1 } },
        { fields: { user_id: 1 } },
        { fields: { sent_at: -1 } },
        { fields: { notification_type: 1 } }
      ],
      apiEndpoints: {
        list: "GET /api/notifications",
        get: "GET /api/notifications/:id",
        create: "POST /api/notifications"
      }
    },

    api_keys: {
      description: "API keys for customer integrations",
      fields: {
        _id: { type: "ObjectId", auto: true, primary: true },
        customer_id: { type: "ObjectId", required: true, ref: "customers" },
        key_hash: { type: "String", required: true, unique: true, sensitive: true },
        key_name: { type: "String" },
        status: { type: "String", enum: ["active", "inactive", "revoked"], default: "active" },
        created_by: { type: "String", ref: "company_users.user_id" },
        last_used: { type: "Date" },
        expires_at: { type: "Date" },
        created_at: { type: "Date", default: "now" }
      },
      indexes: [
        { fields: { key_hash: 1 }, unique: true },
        { fields: { customer_id: 1 } },
        { fields: { status: 1 } },
        { fields: { expires_at: 1 } }
      ],
      relationships: {
        belongsTo: { collection: "customers", foreignKey: "customer_id" }
      },
      apiEndpoints: {
        list: "GET /api/customers/:customerId/api-keys",
        create: "POST /api/customers/:customerId/api-keys",
        revoke: "DELETE /api/api-keys/:id"
      }
    }
  },

  // ================================================================
  // COMMON API PATTERNS
  // ================================================================

  commonEndpoints: {
    auth: {
      login: "POST /api/auth/login",
      logout: "POST /api/auth/logout",
      refresh: "POST /api/auth/refresh",
      forgotPassword: "POST /api/auth/forgot-password",
      resetPassword: "POST /api/auth/reset-password"
    },
    
    dashboard: {
      overview: "GET /api/dashboard/overview",
      stats: "GET /api/dashboard/stats",
      recentActivity: "GET /api/dashboard/recent-activity"
    },

    reports: {
      usage: "GET /api/reports/usage",
      revenue: "GET /api/reports/revenue",
      customers: "GET /api/reports/customers",
      transactions: "GET /api/reports/transactions"
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
      customerIsolation: "Users can only access data for their customer_id",
      systemAdminAccess: "system_admins have access to all customer data"
    },
    
    audit: {
      logAllChanges: "Log all CREATE, UPDATE, DELETE operations to audit_logs",
      sensitiveFields: "Don't log password_hash or key_hash in audit logs",
      retention: "Keep audit logs for 7 years for compliance"
    }
  },

  // ================================================================
  // SAMPLE QUERIES
  // ================================================================

  sampleQueries: {
    mongodb: {
      getCustomerWithActiveSubscription: `
        db.customers.aggregate([
          {
            $lookup: {
              from: "subscriptions",
              localField: "_id",
              foreignField: "customer_id",
              as: "subscriptions"
            }
          },
          {
            $match: {
              "subscriptions.status": "active"
            }
          }
        ])
      `,
      
      getSubscriptionUsage: `
        db.subscriptions.findOne(
          { _id: ObjectId("...") },
          { "usage_periods": { $slice: -1 } }
        )
      `,
      
      getMonthlyTransactions: `
        db.translation_transactions.aggregate([
          {
            $match: {
              transaction_date: {
                $gte: new Date("2025-01-01"),
                $lt: new Date("2025-02-01")
              }
            }
          },
          {
            $group: {
              _id: "$customer_id",
              total_units: { $sum: "$units_consumed" },
              total_transactions: { $sum: 1 }
            }
          }
        ])
      `,
      
      getOverdueInvoices: `
        db.invoices.find({
          status: { $in: ["sent", "pending"] },
          due_date: { $lt: new Date() }
        })
      `
    },
    
    postgresql: {
      getCustomerWithActiveSubscription: `
        SELECT c.*, s.*
        FROM customers c
        INNER JOIN subscriptions s ON c.customer_id = s.customer_id
        WHERE s.status = 'active'
      `,
      
      getSubscriptionUsage: `
        SELECT su.*
        FROM subscription_usage su
        WHERE su.subscription_id = $1
        ORDER BY su.period_start DESC
        LIMIT 1
      `,
      
      getMonthlyTransactions: `
        SELECT 
          customer_id,
          SUM(units_consumed) as total_units,
          COUNT(*) as total_transactions
        FROM translation_transactions
        WHERE transaction_date >= '2025-01-01'
          AND transaction_date < '2025-02-01'
        GROUP BY customer_id
      `,
      
      getOverdueInvoices: `
        SELECT *
        FROM invoices
        WHERE status IN ('sent', 'pending')
          AND due_date < CURRENT_DATE
      `
    }
  },

  // ================================================================
  // API RESPONSE FORMATS
  // ================================================================

  responseFormats: {
    success: {
      structure: {
        success: true,
        data: "object or array",
        message: "optional success message",
        metadata: {
          page: "for pagination",
          limit: "for pagination",
          total: "total count"
        }
      },
      example: {
        success: true,
        data: { _id: "123", company_name: "Acme Corp" },
        message: "Customer retrieved successfully"
      }
    },
    
    error: {
      structure: {
        success: false,
        error: {
          code: "error code",
          message: "human readable message",
          details: "optional additional details"
        }
      },
      example: {
        success: false,
        error: {
          code: "INSUFFICIENT_UNITS",
          message: "Not enough units available in subscription",
          details: { available: 100, required: 250 }
        }
      }
    }
  },

  // ================================================================
  // MIDDLEWARE & AUTHENTICATION
  // ================================================================

  middleware: {
    authentication: {
      jwt: "Use JWT tokens for authentication",
      strategy: "Bearer token in Authorization header",
      expiry: "Access token: 1 hour, Refresh token: 7 days"
    },
    
    authorization: {
      checkCustomerAccess: "Verify user belongs to customer",
      checkPermissionLevel: "Verify user has required permission_level",
      checkSystemAdmin: "Verify system_admin role for admin endpoints"
    },
    
    validation: {
      requestValidation: "Validate all request bodies against schema",
      sanitization: "Sanitize inputs to prevent injection attacks",
      rateLimit: "Rate limit: 100 requests per minute per API key"
    },
    
    logging: {
      requestLogging: "Log all API requests",
      errorLogging: "Log all errors with stack traces",
      auditLogging: "Log data changes to audit_logs"
    }
  }
};

// Export for use in API generation
if (typeof module !== 'undefined' && module.exports) {
  module.exports = translationSchema;
}

