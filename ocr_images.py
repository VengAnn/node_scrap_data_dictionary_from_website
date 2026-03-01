import sqlite3
import subprocess
import os
import glob
import sys
import shutil

def process_images():
    db_path = "dictionary.db"
    images_dir = "images"
    
    if not os.path.exists(db_path):
        print("Database not found.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if not os.path.isdir(images_dir):
        print(f"Directory '{images_dir}' not found.")
        return

    image_files = glob.glob(os.path.join(images_dir, "*.*"))
    image_files = [f for f in image_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    total = len(image_files)
    print(f"Total images to process: {total}")
    
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = os.path.abspath(".")
    
    success_count = 0
    not_found_in_db = 0
    
    for i, img_path in enumerate(image_files, 1):
        filename = os.path.basename(img_path)
        local_path_db = f"images/{filename}"
        
        cursor.execute("SELECT id, definition_text FROM definitions WHERE local_image_path = ? OR local_image_path = ?", (local_path_db, filename))
        rows = cursor.fetchall()
        
        if not rows:
            cursor.execute("SELECT id, definition_text FROM definitions WHERE id = ?", (os.path.splitext(filename)[0],))
            rows = cursor.fetchall()
            
        if not rows:
            print(f"[{i}/{total}] Skipping {filename}, no matching DB entry found.")
            not_found_in_db += 1
            os.remove(img_path) # if no matching DB entry, maybe just remove it? We'll delete it to clean up
            continue
            
        # Extract text via Tesseract
        try:
            result = subprocess.run(
                ["tesseract", img_path, "stdout", "-l", "khm", "--tessdata-dir", os.path.abspath(".")],
                capture_output=True,
                text=True,
                env=env,
                check=True
            )
            text = result.stdout.strip()
            
            # Update all matched rows
            for row in rows:
                def_id = row[0]
                existing_text = row[1] or ""
                new_text = existing_text + "\n" + text if existing_text else text
                new_text = new_text.strip()
                
                cursor.execute(
                    "UPDATE definitions SET definition_text = ?, local_image_path = NULL, khmer_image_url = NULL WHERE id = ?",
                    (new_text, def_id)
                )
            
            # Remove the image file
            os.remove(img_path)
            success_count += 1
            
            if i % 100 == 0:
                print(f"Processed {i}/{total} images...")
                conn.commit()
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    conn.commit()
    conn.close()
    
    # Try removing the images directory if it's empty
    try:
        shutil.rmtree(images_dir)
        print(f"Removed '{images_dir}' directory as all images were processed.")
    except Exception as e:
        print(f"Could not remove directory '{images_dir}': {e}")
    
    print(f"Done! Successfully converted and deleted {success_count} images. {not_found_in_db} deleted without DB match.")

if __name__ == "__main__":
    process_images()
