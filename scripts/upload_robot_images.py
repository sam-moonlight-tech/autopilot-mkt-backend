#!/usr/bin/env python3
"""Upload robot images from frontend public folder to Supabase storage and update database.

This script:
1. Reads robot images from the frontend public folder
2. Uploads them to Supabase storage bucket (robot-images)
3. Updates the robot_catalog table with the public image URLs (comma-separated)

Usage:
    python scripts/upload_robot_images.py

Requirements:
    - SUPABASE_URL and SUPABASE_SECRET_KEY environment variables must be set
    - The 'robot-images' storage bucket must exist in Supabase (public bucket)
    - Frontend public folder must exist at ../Autopilot-Marketplace-Discovery-to-Greenlight-/public/
    - Database must have robot_catalog table populated with robots

Note:
    - Images are stored in Supabase storage at: robots/{robot_id}/{filename}
    - Multiple images per robot are stored as comma-separated URLs in the database
    - If bucket doesn't exist, the script will provide instructions to create it manually
"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import Client

from src.core.config import get_settings
from src.core.supabase import get_supabase_client


# Mapping of robot names (from database) to image file prefixes
# Keys are normalized (lowercase) for matching, values are the actual prefixes to search for
# Based on actual files in the public folder
ROBOT_IMAGE_MAPPING: dict[str, list[str]] = {
    "cc1": ["cc1-1", "cc1-3"],  # cc1-2 doesn't exist
    "cc1 pro": ["cc1-pro-1", "cc1-pro-2", "cc1-pro-3"],
    "mt1 vac": ["mt1-vac-1", "mt1-vac-2"],  # mt1-vac-3 doesn't exist
    "kleenbot c30": ["Kleenbot-C30-1", "Kleenbot-C30-2", "Kleenbot-C30-3"],
    "kleenbot c40": ["Kleenbot-C40-1", "Kleenbot-C40-2", "Kleenbot-C40-3"],  # C40-2 has no extension
    "kas": ["Kas-2", "Kas-3"],  # Kas-1 doesn't exist
    "neo 2w": ["Neo2W-2-1", "NeoDSX-2-2"],  # Neo2W-3 doesn't exist, using NeoDSX-2-2
    "t380amr": ["T380AMR-2", "T380AMR-3"],
    "t7amr": ["T7AMR", "T7AMR-2", "T7AMR-3"],
    "phantas": ["Gausium-Phantas-1", "Gausium-Phantas-2", "Gausium-Phantas-3"],
    "vacuum 40": ["Vacuum-40-1", "Vacuum-40-2", "Vacuum-40-3"],
    "pudu t300": ["PUDU-T300-1"],
    "pudu t600": ["Pudu-T600-1", "Pudu-T600-2"],
}

# Storage bucket name
STORAGE_BUCKET = "robot-images"


def find_image_files(public_dir: Path, prefix: str) -> list[Path]:
    """Find image files matching the given prefix.
    
    Args:
        public_dir: Path to the public directory containing images
        prefix: Image file prefix to search for
        
    Returns:
        List of matching image file paths (no duplicates)
    """
    extensions = [".webp", ".jpg", ".jpeg", ".png"]
    matches = set()  # Use set to avoid duplicates
    
    for ext in extensions:
        # Try exact match first
        exact_path = public_dir / f"{prefix}{ext}"
        if exact_path.exists():
            matches.add(exact_path)
            continue
        
        # Try case variations with glob
        for file_path in public_dir.glob(f"{prefix}*{ext}"):
            if file_path.name.lower().startswith(prefix.lower()):
                matches.add(file_path)
    
    # Also check without extension (some files like Kleenbot-C40-2 have no extension)
    no_ext_path = public_dir / prefix
    if no_ext_path.exists() and no_ext_path.is_file():
        matches.add(no_ext_path)
    
    # Try case-insensitive glob for files without extension
    for file_path in public_dir.glob(f"{prefix}*"):
        if file_path.is_file() and not file_path.suffix and file_path.name.lower().startswith(prefix.lower()):
            matches.add(file_path)
    
    return sorted(matches)


def upload_image_to_storage(
    client: Client, bucket: str, file_path: Path, storage_path: str
) -> str:
    """Upload an image file to Supabase storage.
    
    Args:
        client: Supabase client
        bucket: Storage bucket name
        file_path: Local file path to upload
        storage_path: Path in storage bucket
        
    Returns:
        Public URL of the uploaded file
    """
    with open(file_path, "rb") as f:
        file_data = f.read()
    
    # Determine content type
    ext = file_path.suffix.lower()
    content_type_map = {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    content_type = content_type_map.get(ext, "image/jpeg")
    
    # Upload the file - Supabase Python client will raise exception on error
    try:
        result = client.storage.from_(bucket).upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        # If upload raises an exception, re-raise with context
        raise Exception(f"Failed to upload {file_path.name}: {e}")
    
    # Get public URL - construct it manually as Supabase Python client API may vary
    settings = get_settings()
    public_url = f"{settings.supabase_url}/storage/v1/object/public/{bucket}/{storage_path}"
    
    return public_url


def ensure_bucket_exists(client: Client, bucket_name: str) -> None:
    """Ensure the storage bucket exists, create if it doesn't.
    
    Args:
        client: Supabase client
        bucket_name: Name of the bucket to check/create
    """
    try:
        # Try to list files in the bucket to check if it exists
        result = client.storage.from_(bucket_name).list()
        print(f"✓ Bucket '{bucket_name}' already exists")
    except Exception:
        # Bucket doesn't exist, create it
        print(f"Creating storage bucket '{bucket_name}'...")
        try:
            # Note: Creating buckets via API may require admin privileges
            # If this fails, the bucket needs to be created manually in Supabase dashboard
            result = client.storage.create_bucket(
                bucket_name,
                options={"public": True, "file_size_limit": 10485760}  # 10MB limit
            )
            if hasattr(result, "error") and result.error:
                raise Exception(f"Failed to create bucket: {result.error}")
            print(f"✓ Created bucket '{bucket_name}'")
        except Exception as e:
            print(f"⚠️  Could not create bucket automatically: {e}")
            print(f"   Please create bucket '{bucket_name}' manually in Supabase dashboard")
            print(f"   Make sure it's set to public and has appropriate file size limits")
            raise


def update_robot_image_url(client: Client, robot_id: str, image_urls: list[str]) -> None:
    """Update robot's image_url in the database.
    
    Args:
        client: Supabase client
        robot_id: UUID of the robot
        image_urls: List of image URLs (will be stored as comma-separated)
    """
    # Store as comma-separated string
    image_url_str = ",".join(image_urls)
    
    try:
        result = client.table("robot_catalog").update({
            "image_url": image_url_str
        }).eq("id", robot_id).execute()
        
        if not result.data:
            raise Exception(f"No data returned from update operation")
    except Exception as e:
        raise Exception(f"Failed to update robot {robot_id}: {e}")
    
    print(f"  ✓ Updated database with {len(image_urls)} image(s)")


def main() -> None:
    """Main execution function."""
    print("🚀 Starting robot image upload process...\n")
    
    # Get paths
    backend_root = Path(__file__).parent.parent
    frontend_root = backend_root.parent / "Autopilot-Marketplace-Discovery-to-Greenlight-"
    public_dir = frontend_root / "public"
    
    if not public_dir.exists():
        print(f"❌ Error: Public directory not found at {public_dir}")
        sys.exit(1)
    
    print(f"📁 Using public directory: {public_dir}\n")
    
    # Get Supabase client
    try:
        client = get_supabase_client()
    except Exception as e:
        print(f"❌ Error: Failed to initialize Supabase client: {e}")
        sys.exit(1)
    
    # Ensure bucket exists
    try:
        ensure_bucket_exists(client, STORAGE_BUCKET)
    except Exception as e:
        print(f"❌ Error: Failed to ensure bucket exists: {e}")
        print(f"\n💡 Tip: Create the bucket manually in Supabase Dashboard:")
        print(f"   1. Go to Storage in your Supabase project")
        print(f"   2. Click 'New bucket'")
        print(f"   3. Name it: {STORAGE_BUCKET}")
        print(f"   4. Make it public")
        print(f"   5. Run this script again")
        sys.exit(1)
    
    # Get all robots from database
    print("\n📋 Fetching robots from database...")
    try:
        robots_result = client.table("robot_catalog").select("id, name").execute()
        robots = robots_result.data or []
        print(f"✓ Found {len(robots)} robots in database\n")
    except Exception as e:
        print(f"❌ Error: Failed to fetch robots: {e}")
        sys.exit(1)
    
    # Process each robot
    updated_count = 0
    skipped_count = 0
    
    for robot in robots:
        robot_name = robot["name"]
        robot_id = robot["id"]
        
        print(f"🤖 Processing: {robot_name} ({robot_id[:8]}...)")
        
        # Find matching image prefixes (case-insensitive matching)
        normalized_name = robot_name.lower().strip()
        matching_prefixes = ROBOT_IMAGE_MAPPING.get(normalized_name)
        
        # Try partial matching if exact match not found
        if not matching_prefixes:
            for mapped_name, prefixes in ROBOT_IMAGE_MAPPING.items():
                if mapped_name in normalized_name or normalized_name in mapped_name:
                    matching_prefixes = prefixes
                    print(f"  ℹ️  Using partial match: '{mapped_name}' for '{robot_name}'")
                    break
        
        if not matching_prefixes:
            print(f"  ⚠️  No image mapping found for '{robot_name}', skipping...")
            print(f"      Available mappings: {', '.join(sorted(ROBOT_IMAGE_MAPPING.keys()))}")
            skipped_count += 1
            continue
        
        # Find image files
        all_images = []
        for prefix in matching_prefixes:
            images = find_image_files(public_dir, prefix)
            all_images.extend(images)
        
        if not all_images:
            print(f"  ⚠️  No image files found for '{robot_name}', skipping...")
            skipped_count += 1
            continue
        
        # Upload images and collect URLs
        image_urls = []
        for img_path in all_images:
            # Create storage path: robots/{robot_id}/{filename}
            storage_path = f"robots/{robot_id}/{img_path.name}"
            
            try:
                print(f"  📤 Uploading {img_path.name}...")
                public_url = upload_image_to_storage(client, STORAGE_BUCKET, img_path, storage_path)
                image_urls.append(public_url)
                print(f"    ✓ Uploaded: {public_url}")
            except Exception as e:
                print(f"    ❌ Failed to upload {img_path.name}: {e}")
                continue
        
        if not image_urls:
            print(f"  ❌ No images were successfully uploaded for '{robot_name}'")
            skipped_count += 1
            continue
        
        # Update database
        try:
            update_robot_image_url(client, robot_id, image_urls)
            updated_count += 1
        except Exception as e:
            print(f"  ❌ Failed to update database: {e}")
            skipped_count += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print(f"✅ Complete!")
    print(f"   Updated: {updated_count} robots")
    print(f"   Skipped: {skipped_count} robots")
    print("=" * 60)


if __name__ == "__main__":
    main()

