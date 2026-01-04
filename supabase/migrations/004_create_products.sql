-- Create products table
-- Stores robotics product information with reference to Pinecone embeddings

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    specs JSONB DEFAULT '{}',
    pricing JSONB DEFAULT '{}',
    image_url TEXT,
    manufacturer VARCHAR(255),
    model_number VARCHAR(100),
    embedding_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for products
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_embedding_id ON products(embedding_id);
CREATE INDEX IF NOT EXISTS idx_products_manufacturer ON products(manufacturer);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);

-- Enable Row Level Security
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS Policies for products
-- Products are publicly readable for MVP

-- Policy: Anyone can read products
CREATE POLICY "Products are publicly readable"
    ON products FOR SELECT
    USING (true);

-- Policy: Service role can manage products
CREATE POLICY "Service role can manage products"
    ON products FOR ALL
    USING (auth.role() = 'service_role');

-- Insert some sample products for testing
INSERT INTO products (name, description, category, manufacturer, specs, pricing) VALUES
(
    'UR10e Collaborative Robot',
    'Versatile cobot for heavy-duty applications with 10kg payload capacity. Perfect for palletizing, machine tending, and packaging tasks.',
    'collaborative_robot',
    'Universal Robots',
    '{"payload_kg": 10, "reach_mm": 1300, "repeatability_mm": 0.05, "weight_kg": 33.5, "power_consumption_w": 350}',
    '{"base_price_usd": 45000, "installation_usd": 5000, "training_usd": 2500}'
),
(
    'UR5e Collaborative Robot',
    'Compact and versatile cobot for light-duty tasks with 5kg payload. Ideal for assembly, pick and place, and quality inspection.',
    'collaborative_robot',
    'Universal Robots',
    '{"payload_kg": 5, "reach_mm": 850, "repeatability_mm": 0.03, "weight_kg": 20.6, "power_consumption_w": 200}',
    '{"base_price_usd": 35000, "installation_usd": 4000, "training_usd": 2000}'
),
(
    'Fanuc CRX-10iA/L',
    'Long-reach collaborative robot with 10kg payload and 1418mm reach. Features intuitive direct teaching and IP67 protection.',
    'collaborative_robot',
    'Fanuc',
    '{"payload_kg": 10, "reach_mm": 1418, "repeatability_mm": 0.04, "weight_kg": 40, "protection": "IP67"}',
    '{"base_price_usd": 55000, "installation_usd": 6000, "training_usd": 3000}'
),
(
    'MiR250 Mobile Robot',
    'Agile autonomous mobile robot for internal logistics with 250kg payload. Features built-in sensors and fleet management.',
    'amr',
    'Mobile Industrial Robots',
    '{"payload_kg": 250, "speed_mps": 2.0, "battery_hours": 10, "navigation": "SLAM", "safety": "Category 3 PLd"}',
    '{"base_price_usd": 30000, "installation_usd": 8000, "fleet_software_usd": 15000}'
),
(
    'Boston Dynamics Spot',
    'Agile mobile robot for inspection and data capture. Features all-terrain mobility and modular payload system.',
    'inspection_robot',
    'Boston Dynamics',
    '{"payload_kg": 14, "speed_mps": 1.6, "runtime_hours": 1.5, "protection": "IP54", "terrain": "all_terrain"}',
    '{"base_price_usd": 74500, "enterprise_edition_usd": 149500}'
),
(
    'Kuka KR 16 R2010',
    'Industrial robot for arc welding and handling with 16kg payload and 2010mm reach. High precision and speed.',
    'industrial_robot',
    'Kuka',
    '{"payload_kg": 16, "reach_mm": 2010, "repeatability_mm": 0.05, "axes": 6, "protection": "IP65"}',
    '{"base_price_usd": 50000, "installation_usd": 10000, "programming_usd": 5000}'
),
(
    'ABB IRB 2600',
    'Versatile industrial robot for material handling and machine tending. 20kg payload with compact footprint.',
    'industrial_robot',
    'ABB',
    '{"payload_kg": 20, "reach_mm": 1650, "repeatability_mm": 0.05, "axes": 6, "cycle_time_s": 0.4}',
    '{"base_price_usd": 48000, "installation_usd": 8000}'
),
(
    'Cognex In-Sight D900',
    'Deep learning vision system for complex inspection tasks. Handles OCR, defect detection, and assembly verification.',
    'vision_system',
    'Cognex',
    '{"resolution_mp": 2.3, "frame_rate_fps": 60, "deep_learning": true, "interface": "ethernet"}',
    '{"base_price_usd": 8500, "software_license_usd": 3000}'
),
(
    'Schunk EGP 64-N-N-B',
    'Electric parallel gripper for collaborative robot applications. 64mm stroke with integrated electronics.',
    'end_effector',
    'Schunk',
    '{"stroke_mm": 64, "gripping_force_n": 60, "weight_kg": 0.45, "protocol": "profinet"}',
    '{"base_price_usd": 4500}'
),
(
    'OnRobot RG6',
    'Flexible gripper for collaborative robots with 6kg payload capacity. Dual-gripper option available.',
    'end_effector',
    'OnRobot',
    '{"stroke_mm": 160, "gripping_force_n": 120, "weight_kg": 1.18, "fingertip_options": 6}',
    '{"base_price_usd": 5800, "dual_gripper_usd": 9800}'
);
