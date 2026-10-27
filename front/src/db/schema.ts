import {
  pgTable, uuid, varchar, text, boolean, integer,
  timestamp, jsonb, unique,
} from 'drizzle-orm/pg-core'
import { sql } from 'drizzle-orm'

const now = () => sql`now()`

// ── Users ─────────────────────────────────────────────────────────────────────
export const users = pgTable('users', {
  id:           uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  email:        varchar('email', { length: 255 }).unique().notNull(),
  passwordHash: text('password_hash'),           // null para usuarios migrados de Supabase
  name:         varchar('name', { length: 255 }),
  role:         varchar('role', { length: 50 }).default('workspace_owner'),
  isActive:     boolean('is_active').default(true),
  lastLoginAt:  timestamp('last_login_at', { withTimezone: true }),
  createdAt:    timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:    timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Workspaces ────────────────────────────────────────────────────────────────
export const workspaces = pgTable('workspaces', {
  id:           uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  name:         varchar('name', { length: 255 }).notNull(),
  legalName:    varchar('legal_name', { length: 255 }),
  slug:         varchar('slug', { length: 255 }).unique().notNull(),
  businessType: varchar('business_type', { length: 50 }),
  country:      varchar('country', { length: 2 }).default('CO'),
  timezone:     varchar('timezone', { length: 50 }).notNull(),
  primaryPhone: varchar('primary_phone', { length: 20 }),
  primaryEmail: varchar('primary_email', { length: 255 }),
  brandColor:   varchar('brand_color', { length: 7 }),
  logoUrl:      text('logo_url'),
  isActive:     boolean('is_active').default(true),
  createdAt:    timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:    timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Workspace Members ─────────────────────────────────────────────────────────
export const workspaceMembers = pgTable('workspace_members', {
  id:          uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId: uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  userId:      uuid('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  memberRole:  varchar('member_role', { length: 50 }).notNull(),
  status:      varchar('status', { length: 50 }).default('active'),
  joinedAt:    timestamp('joined_at', { withTimezone: true }),
  createdAt:   timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:   timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Channels ──────────────────────────────────────────────────────────────────
export const channels = pgTable('channels', {
  id:                 uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:        uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  channelType:        varchar('channel_type', { length: 50 }).default('whatsapp'),
  provider:           varchar('provider', { length: 100 }).notNull(),
  phoneNumber:        varchar('phone_number', { length: 20 }).notNull(),
  phoneNumberId:      varchar('phone_number_id', { length: 255 }),
  displayName:        varchar('display_name', { length: 255 }),
  status:             varchar('status', { length: 50 }).default('active'),
  coexistenceEnabled: boolean('coexistence_enabled').default(true),
  externalAccountId:  varchar('external_account_id', { length: 255 }),
  metadata:           jsonb('metadata'),
  createdAt:          timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:          timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Calendars ─────────────────────────────────────────────────────────────────
export const calendars = pgTable('calendars', {
  id:                          uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:                 uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  name:                        varchar('name', { length: 255 }).notNull(),
  googleCalendarId:            varchar('google_calendar_id', { length: 255 }).notNull(),
  connectedByUserId:           uuid('connected_by_user_id').references(() => users.id),
  oauthRefreshTokenEncrypted:  text('oauth_refresh_token_encrypted'),
  syncEnabled:                 boolean('sync_enabled').default(true),
  syncStatus:                  varchar('sync_status', { length: 50 }).default('active'),
  lastSyncedAt:                timestamp('last_synced_at', { withTimezone: true }),
  createdAt:                   timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:                   timestamp('updated_at', { withTimezone: true }).default(now()),
}, (t) => [unique().on(t.workspaceId, t.googleCalendarId)])

// ── Services ──────────────────────────────────────────────────────────────────
export const services = pgTable('services', {
  id:                      uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:             uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  name:                    varchar('name', { length: 255 }).notNull(),
  description:             text('description'),
  durationMinutes:         integer('duration_minutes').notNull(),
  bufferMinutes:           integer('buffer_minutes').default(0),
  priceCop:                integer('price_cop').notNull(),
  homeServiceEnabled:      boolean('home_service_enabled').default(false),
  homeServiceExtraMinutes: integer('home_service_extra_minutes').default(0),
  homeServiceExtraPriceCop: integer('home_service_extra_price_cop').default(0),
  isActive:                boolean('is_active').default(true),
  createdAt:               timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:               timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Customers ─────────────────────────────────────────────────────────────────
export const customers = pgTable('customers', {
  id:             uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:    uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  phone:          varchar('phone', { length: 20 }).notNull(),
  name:           varchar('name', { length: 255 }),
  email:          varchar('email', { length: 255 }),
  notes:          text('notes'),
  lastSeenAt:     timestamp('last_seen_at', { withTimezone: true }),
  sourceChannelId: uuid('source_channel_id').references(() => channels.id),
  createdAt:      timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:      timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Appointments ──────────────────────────────────────────────────────────────
export const appointments = pgTable('appointments', {
  id:                  uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:         uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  customerId:          uuid('customer_id').notNull().references(() => customers.id),
  serviceId:           uuid('service_id').notNull().references(() => services.id),
  channelId:           uuid('channel_id').notNull().references(() => channels.id),
  calendarId:          uuid('calendar_id').notNull().references(() => calendars.id),
  startAt:             timestamp('start_at', { withTimezone: true }).notNull(),
  endAt:               timestamp('end_at', { withTimezone: true }).notNull(),
  status:              varchar('status', { length: 50 }).default('pending'),
  priceCop:            integer('price_cop').notNull(),
  homeServicePriceCop: integer('home_service_price_cop').default(0),
  isHomeService:       boolean('is_home_service').default(false),
  homeAddress:         varchar('home_address', { length: 500 }),
  googleEventId:       varchar('google_event_id', { length: 255 }),
  cancellationReason:  varchar('cancellation_reason', { length: 255 }),
  cancelledBy:         uuid('cancelled_by').references(() => users.id),
  createdBy:           uuid('created_by').references(() => users.id),
  confirmedAt:         timestamp('confirmed_at', { withTimezone: true }),
  cancelledAt:         timestamp('cancelled_at', { withTimezone: true }),
  createdAt:           timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:           timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Availability Blocks ───────────────────────────────────────────────────────
export const availabilityBlocks = pgTable('availability_blocks', {
  id:          uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId: uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  calendarId:  uuid('calendar_id').notNull().references(() => calendars.id),
  startAt:     timestamp('start_at', { withTimezone: true }).notNull(),
  endAt:       timestamp('end_at', { withTimezone: true }).notNull(),
  blockType:   varchar('block_type', { length: 50 }).notNull(),
  reason:      varchar('reason', { length: 500 }),
  source:      varchar('source', { length: 50 }),
  googleEventId: varchar('google_event_id', { length: 255 }),
  createdBy:   uuid('created_by').references(() => users.id),
  createdAt:   timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:   timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Conversations ─────────────────────────────────────────────────────────────
export const conversations = pgTable('conversations', {
  id:             uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:    uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  channelId:      uuid('channel_id').notNull().references(() => channels.id),
  customerId:     uuid('customer_id').references(() => customers.id),
  status:         varchar('status', { length: 50 }).default('open'),
  currentIntent:  varchar('current_intent', { length: 255 }),
  lastMessageAt:  timestamp('last_message_at', { withTimezone: true }),
  lastAgentState: text('last_agent_state'),
  needsReview:    boolean('needs_review').default(false),
  customerPhone:  varchar('customer_phone', { length: 20 }),
  createdAt:      timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:      timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Messages ──────────────────────────────────────────────────────────────────
export const messages = pgTable('messages', {
  id:                uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:       uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  conversationId:    uuid('conversation_id').notNull().references(() => conversations.id, { onDelete: 'cascade' }),
  channelId:         uuid('channel_id').notNull().references(() => channels.id),
  customerId:        uuid('customer_id').references(() => customers.id),
  direction:         varchar('direction', { length: 50 }).notNull(),
  senderType:        varchar('sender_type', { length: 50 }).notNull(),
  messageType:       varchar('message_type', { length: 50 }),
  content:           text('content'),
  mediaUrl:          text('media_url'),
  providerMessageId: varchar('provider_message_id', { length: 255 }),
  status:            varchar('status', { length: 50 }),
  sentAt:            timestamp('sent_at', { withTimezone: true }),
  receivedAt:        timestamp('received_at', { withTimezone: true }),
  createdAt:         timestamp('created_at', { withTimezone: true }).default(now()),
})

// ── Billing Plans ─────────────────────────────────────────────────────────────
export const billingPlans = pgTable('billing_plans', {
  id:              uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  name:            varchar('name', { length: 255 }).notNull(),
  description:     text('description'),
  priceCop:        integer('price_cop').notNull(),
  billingInterval: varchar('billing_interval', { length: 50 }),
  maxChannels:     integer('max_channels'),
  maxCalendars:    integer('max_calendars'),
  maxServices:     integer('max_services'),
  maxMessages:     integer('max_messages'),
  features:        jsonb('features'),
  isActive:        boolean('is_active').default(true),
  createdAt:       timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:       timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Subscriptions ─────────────────────────────────────────────────────────────
export const subscriptions = pgTable('subscriptions', {
  id:                 uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId:        uuid('workspace_id').notNull().unique().references(() => workspaces.id, { onDelete: 'cascade' }),
  billingPlanId:      uuid('billing_plan_id').notNull().references(() => billingPlans.id),
  status:             varchar('status', { length: 50 }).notNull(),
  paymentMethod:      varchar('payment_method', { length: 100 }),
  paidThisMonth:      boolean('paid_this_month').default(false),
  currentPeriodStart: timestamp('current_period_start', { withTimezone: true }),
  currentPeriodEnd:   timestamp('current_period_end', { withTimezone: true }),
  nextBillingDate:    timestamp('next_billing_date', { withTimezone: true }),
  paymentVerifiedBy:  uuid('payment_verified_by').references(() => users.id),
  notes:              text('notes'),
  createdAt:          timestamp('created_at', { withTimezone: true }).default(now()),
  updatedAt:          timestamp('updated_at', { withTimezone: true }).default(now()),
})

// ── Audit Logs ────────────────────────────────────────────────────────────────
export const auditLogs = pgTable('audit_logs', {
  id:          uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  workspaceId: uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  actorUserId: uuid('actor_user_id').references(() => users.id),
  action:      varchar('action', { length: 255 }).notNull(),
  entityType:  varchar('entity_type', { length: 100 }).notNull(),
  entityId:    varchar('entity_id', { length: 255 }),
  beforeData:  jsonb('before_data'),
  afterData:   jsonb('after_data'),
  createdAt:   timestamp('created_at', { withTimezone: true }).default(now()),
})
