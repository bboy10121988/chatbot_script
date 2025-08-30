-- MySQL 8.0+ recommended
-- Charset/Collation: utf8mb4/utf8mb4_0900_ai_ci

CREATE DATABASE IF NOT EXISTS chatbot DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE chatbot;

-- Tenants (multi-tenant support)
CREATE TABLE IF NOT EXISTS tenants (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  name          VARCHAR(120) NOT NULL,
  status        ENUM('active','disabled') NOT NULL DEFAULT 'active',
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- API keys (hashed)
CREATE TABLE IF NOT EXISTS api_keys (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  key_hash        VARBINARY(64) NOT NULL, -- store hash (e.g., bcrypt/argon2 encoded bytes)
  label           VARCHAR(120) NULL,
  rate_limit_rpm  INT NOT NULL DEFAULT 60,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB;

-- Products
CREATE TABLE IF NOT EXISTS products (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id   BIGINT NOT NULL,
  sku         VARCHAR(64) UNIQUE,
  name        VARCHAR(255) NOT NULL,
  description TEXT NULL,
  price       DECIMAL(10,2) NOT NULL,
  currency    CHAR(3) NOT NULL DEFAULT 'CNY',
  image_url   VARCHAR(512) NULL,
  stock       INT NOT NULL DEFAULT 0,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  tags        JSON NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_products_tenant (tenant_id),
  FULLTEXT INDEX ftx_products_name_desc (name, description),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB;

-- Keyword rules
CREATE TABLE IF NOT EXISTS keyword_rules (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id      BIGINT NOT NULL,
  trigger_text   VARCHAR(255) NOT NULL,
  match_type     ENUM('exact','prefix','contains','regex') NOT NULL DEFAULT 'contains',
  locale         VARCHAR(10) NULL,
  priority       INT NOT NULL DEFAULT 0,
  product_ids    JSON NULL,         -- [product_id, ...]
  response_text  VARCHAR(500) NULL, -- optional assistant copy
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_rules_tenant (tenant_id),
  INDEX idx_rules_trigger (trigger_text),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB;

-- Synonyms
CREATE TABLE IF NOT EXISTS synonyms (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id  BIGINT NOT NULL,
  term       VARCHAR(255) NOT NULL,
  synonyms   JSON NOT NULL, -- ["无线耳机","蓝牙耳机"]
  locale     VARCHAR(10) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_synonyms_tenant (tenant_id),
  INDEX idx_synonyms_term (term),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB;

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id          BIGINT NOT NULL,
  external_user_id   VARCHAR(120) NULL,
  session_token      VARCHAR(120) NULL,
  status             ENUM('open','closed') NOT NULL DEFAULT 'open',
  created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_conv_tenant (tenant_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB;

-- Messages
CREATE TABLE IF NOT EXISTS messages (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  conversation_id  BIGINT NOT NULL,
  role             ENUM('user','assistant','system') NOT NULL,
  content          TEXT NOT NULL,
  content_type     ENUM('text','json') NOT NULL DEFAULT 'text',
  metadata         JSON NULL,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_msgs_conv (conversation_id, created_at),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Carts
CREATE TABLE IF NOT EXISTS carts (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  conversation_id BIGINT NULL,
  external_user_id VARCHAR(120) NULL,
  status          ENUM('open','checked_out','abandoned') NOT NULL DEFAULT 'open',
  currency        CHAR(3) NOT NULL DEFAULT 'CNY',
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_carts_tenant (tenant_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Cart items
CREATE TABLE IF NOT EXISTS cart_items (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  cart_id     BIGINT NOT NULL,
  product_id  BIGINT NOT NULL,
  quantity    INT NOT NULL DEFAULT 1,
  unit_price  DECIMAL(10,2) NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_cart_product (cart_id, product_id),
  FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;

-- Helpful indices for product lookup by tag/name
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

