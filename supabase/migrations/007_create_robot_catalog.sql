-- Create robot_catalog table
-- Stores robot product information for the marketplace

CREATE TABLE IF NOT EXISTS robot_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(50) UNIQUE,
    name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(100),
    category VARCHAR(100) NOT NULL,
    best_for TEXT,
    modes TEXT[] NOT NULL DEFAULT '{}',
    surfaces TEXT[] NOT NULL DEFAULT '{}',
    monthly_lease DECIMAL(10,2) NOT NULL,
    purchase_price DECIMAL(10,2) NOT NULL,
    time_efficiency DECIMAL(3,2) NOT NULL
        CHECK (time_efficiency >= 0 AND time_efficiency <= 1),
    key_reasons TEXT[] NOT NULL DEFAULT '{}',
    specs TEXT[] NOT NULL DEFAULT '{}',
    image_url TEXT,
    stripe_product_id VARCHAR(255) NOT NULL,
    stripe_lease_price_id VARCHAR(255) NOT NULL,
    embedding_id VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for robot_catalog
CREATE INDEX IF NOT EXISTS idx_robot_catalog_active ON robot_catalog(active);
CREATE INDEX IF NOT EXISTS idx_robot_catalog_category ON robot_catalog(category);
CREATE INDEX IF NOT EXISTS idx_robot_catalog_manufacturer ON robot_catalog(manufacturer);
CREATE INDEX IF NOT EXISTS idx_robot_catalog_embedding_id ON robot_catalog(embedding_id);

-- Enable Row Level Security
ALTER TABLE robot_catalog ENABLE ROW LEVEL SECURITY;

-- Policy: Robot catalog is publicly readable
CREATE POLICY "Robot catalog is publicly readable"
    ON robot_catalog FOR SELECT
    USING (true);

-- Policy: Service role has full access
CREATE POLICY "Service role full access to robot_catalog"
    ON robot_catalog FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_robot_catalog_updated_at
    BEFORE UPDATE ON robot_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Seed data from Marketplace MVP Robot SKU database
-- Monthly lease estimated at ~5% of purchase price
-- stripe_product_id and stripe_lease_price_id are placeholders - update with real Stripe IDs

INSERT INTO robot_catalog (sku, name, manufacturer, category, best_for, modes, surfaces, monthly_lease, purchase_price, time_efficiency, key_reasons, specs, stripe_product_id, stripe_lease_price_id)
VALUES
-- Pudu CC1 Pro - Premium 4-in-1 Scrubber
(
    'PUDU-CC1PRO-2025-001',
    'CC1 Pro',
    'Pudu',
    'Premium Scrubber',
    'Large facilities with mixed floors (airports, malls, hospitals)',
    ARRAY['Scrub', 'Vacuum', 'Sweep', 'Mop'],
    ARRAY['Tile', 'Concrete', 'Epoxy'],
    1200.00,
    24000.00,
    0.80,
    ARRAY['4-in-1 cleaning capability', 'Advanced LiDAR + Vision navigation', '24/7 capable with 15 min/day human touch'],
    ARRAY['700-1000 m²/h coverage', '5h runtime', 'LiFePO₄ battery', '70cm min aisle width', 'Auto-docking'],
    'prod_pudu_cc1_pro',
    'price_pudu_cc1_pro_monthly'
),
-- Pudu CC1 - Standard 4-in-1 Scrubber
(
    'PUDU-CC1-2025-001',
    'CC1',
    'Pudu',
    'Multi-Function Scrubber',
    'Offices, retail stores, education facilities',
    ARRAY['Scrub', 'Vacuum', 'Sweep', 'Mop'],
    ARRAY['Tile', 'Concrete', 'Epoxy'],
    1100.00,
    22000.00,
    0.80,
    ARRAY['4-in-1 cleaning capability', 'First-time autonomy friendly', 'Cost-effective multi-surface cleaning'],
    ARRAY['700-1000 m²/h coverage', '5h runtime', 'LiFePO₄ battery', '70cm min aisle width', 'Auto-docking'],
    'prod_pudu_cc1',
    'price_pudu_cc1_monthly'
),
-- Pudu MT1 Vac - Industrial Vacuum
(
    'PUDU-MT1-2025-001',
    'MT1 Vac',
    'Pudu',
    'Industrial Vacuum',
    'Large dry-floor areas (airports, casinos, big malls)',
    ARRAY['Vacuum', 'Sweep'],
    ARRAY['Hard floors', 'Carpet'],
    1050.00,
    21000.00,
    0.80,
    ARRAY['High-speed vacuum coverage up to 1400 m²/h', 'Advanced LiDAR + VSLAM navigation', 'Long 4-5h runtime'],
    ARRAY['Up to 1400 m²/h coverage', '4-5h runtime', 'Li-ion battery', '75cm min aisle width', 'Auto-charging dock'],
    'prod_pudu_mt1_vac',
    'price_pudu_mt1_vac_monthly'
),
-- Avidbots Neo 2W - Enterprise Scrubber
(
    'AVID-NEO2W-2025-001',
    'Neo 2W',
    'Avidbots',
    'Enterprise Scrubber',
    'Warehouses, manufacturing plants (large industrial floors)',
    ARRAY['Scrub'],
    ARRAY['Concrete', 'Tile'],
    3500.00,
    70000.00,
    0.85,
    ARRAY['Industry-leading 2600 m²/h coverage', 'BrainOS navigation', 'Built for 24/7 industrial environments'],
    ARRAY['~2600 m²/h coverage', '3.5h runtime', 'Lead-Acid 36V battery', '1.5m min aisle width', 'Manual docking'],
    'prod_avidbots_neo2w',
    'price_avidbots_neo2w_monthly'
),
-- Avidbots Kas - Compact Scrubber
(
    'AVID-KAS-2025-001',
    'Kas',
    'Avidbots',
    'Compact Scrubber',
    'Education, healthcare, retail (smaller areas, tight spaces)',
    ARRAY['Scrub'],
    ARRAY['Tile', 'Vinyl', 'Concrete'],
    2000.00,
    40000.00,
    0.80,
    ARRAY['Compact design for tight spaces', 'Fast 2h charge time', 'Swappable LiFePO₄ battery'],
    ARRAY['500-1000 m²/h coverage', '3-4h runtime', 'LiFePO₄ swappable battery', '1.0m min aisle width'],
    'prod_avidbots_kas',
    'price_avidbots_kas_monthly'
),
-- Tennant T7AMR - Large Retail Scrubber
(
    'TENN-T7AMR-2025-001',
    'T7AMR',
    'Tennant',
    'Large Retail Scrubber',
    'Supermarkets, big-box retail, malls, airports',
    ARRAY['Scrub'],
    ARRAY['Concrete', 'Tile'],
    3000.00,
    60000.00,
    0.80,
    ARRAY['Industry-proven teach & repeat mode', '6-year useful life', 'Customer-validated performance'],
    ARRAY['~2000 m²/h coverage', '3.7h runtime', 'Lead-Acid or Li-ion options', '~90cm min aisle width'],
    'prod_tennant_t7amr',
    'price_tennant_t7amr_monthly'
),
-- Tennant T380AMR - Mid-Size Scrubber
(
    'TENN-T380AMR-2025-001',
    'T380AMR',
    'Tennant',
    'Mid-Size Scrubber',
    'Mid-size retail stores, schools (narrow aisles)',
    ARRAY['Scrub'],
    ARRAY['Tile', 'Concrete'],
    2000.00,
    40000.00,
    0.80,
    ARRAY['Easy teach & repeat navigation', 'Fits narrow retail aisles', 'Customer-validated reliability'],
    ARRAY['Up to 3106 m²/h coverage', '~3h runtime', 'Lead-Acid or Li-ion options', '75cm min aisle width'],
    'prod_tennant_t380amr',
    'price_tennant_t380amr_monthly'
),
-- Gausium Phantas - All-in-One Cleaner
(
    'GAUS-PHANTAS-2025-001',
    'Phantas',
    'Gausium',
    'All-in-One Cleaner',
    'Offices, hotels, retail (mixed floors, vacuum/scrub)',
    ARRAY['Scrub', 'Vacuum', 'Sweep', 'Mop'],
    ARRAY['Tile', 'Wood', 'Carpet'],
    1620.00,
    32405.00,
    0.60,
    ARRAY['True 4-in-1 cleaning', 'Works on carpet and hard floors', 'Auto-refill docking option'],
    ARRAY['350-700 m²/h coverage', '4-4.5h runtime', 'LiFePO₄ battery', '52-60cm min aisle width', 'Auto-docking'],
    'prod_gausium_phantas',
    'price_gausium_phantas_monthly'
),
-- Gausium Vacuum 40 - Office Vacuum
(
    'GAUS-V40-2025-001',
    'Vacuum 40',
    'Gausium',
    'Office Vacuum',
    'Hotels, hospitality (low-pile carpet & hard floors)',
    ARRAY['Vacuum'],
    ARRAY['Tile', 'Carpet'],
    1000.00,
    20000.00,
    0.30,
    ARRAY['Minimal 5 min/day human touch', 'Self-charging dock', 'Quiet operation for hospitality'],
    ARRAY['~500 m²/h coverage', '3-4h runtime', 'Lithium-ion battery', '60cm min aisle width', 'Auto-charging'],
    'prod_gausium_v40',
    'price_gausium_v40_monthly'
),
-- Keenon Kleenbot C40 - Compact 4-in-1
(
    'KEEN-C40-2025-001',
    'Kleenbot C40',
    'Keenon',
    'Compact Multi-Function',
    'Small-medium retail, offices, hospitals (4-in-1 cleaning)',
    ARRAY['Scrub', 'Vacuum', 'Sweep', 'Mop'],
    ARRAY['Marble', 'Tile', 'Epoxy'],
    875.00,
    17500.00,
    0.80,
    ARRAY['Affordable 4-in-1 solution', 'LiDAR + Vision navigation', 'Swappable battery design'],
    ARRAY['~1100 m²/h coverage', '5h runtime', 'LiFePO₄ swappable battery', '65cm min aisle width'],
    'prod_keenon_c40',
    'price_keenon_c40_monthly'
),
-- Keenon Kleenbot C30 - Budget Vacuum
(
    'KEEN-C30-2025-001',
    'Kleenbot C30',
    'Keenon',
    'Budget Vacuum',
    'Offices, small shops (dry floor cleaning)',
    ARRAY['Vacuum', 'Sweep'],
    ARRAY['Hard floors', 'Carpet'],
    600.00,
    12000.00,
    0.80,
    ARRAY['Lowest entry cost', 'Long 6h runtime', 'Easy deployment (complexity 2/5)'],
    ARRAY['600 m²/h coverage', '6h runtime', 'Lithium-ion battery', '65cm min aisle width', 'Plug-in dock'],
    'prod_keenon_c30',
    'price_keenon_c30_monthly'
);
