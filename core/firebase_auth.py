import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from django.conf import settings
from core.models import User
from wastemanager.models import ProjectArea

# Only initialize once
if not firebase_admin._apps:
    cred_path = os.path.join(settings.BASE_DIR, settings.FIREBASE_CREDENTIALS)
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        print(f"Warning: Firebase credentials file not found at {cred_path}")

def verify_firebase_token(token):
    """
    Verifies the Firebase ID token.
    If valid, it fetches or creates the corresponding local User.
    Returns the User object or None.
    """
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get('uid')
        email = decoded_token.get('email', '')
        phone_number = decoded_token.get('phone_number', '')
        
        # Check if user exists by firebase_uid
        user = User.objects.filter(firebase_uid=uid).first()
        
        if not user:
            # Fallback: check by email or phone
            if email:
                user = User.objects.filter(email=email).first()
            elif phone_number:
                user = User.objects.filter(phone=phone_number).first()
                
            if user:
                # Link existing user
                user.firebase_uid = uid
                user.save()
            else:
                # Fetch user data from Firestore 'users' collection
                try:
                    db = firestore.client()
                    user_doc = db.collection('users').document(uid).get()
                except Exception as e:
                    print(f"Failed to fetch Firestore user: {e}")
                    user_doc = None
                    
                first_name = ''
                last_name = ''
                user_type = 'worker'
                
                if user_doc and user_doc.exists:
                    data = user_doc.to_dict()
                    full_name = data.get('name', '')
                    if full_name:
                        parts = full_name.split(' ', 1)
                        first_name = parts[0]
                        last_name = parts[1] if len(parts) > 1 else ''
                    
                    phone_number = phone_number or data.get('phone', '')
                    user_type = data.get('role', 'worker')
                    
                    # The mobile app fetches ProjectAreas from Django, so assignedAreaId
                    # stored in Firestore is now the local Django integer ID (e.g. 1, 2, 3)
                    assigned_area_id = data.get('assignedAreaId', None)
                    assigned_area = None
                    
                    if assigned_area_id:
                        try:
                            # Find the local ProjectArea by its integer ID
                            assigned_area = ProjectArea.objects.filter(id=int(assigned_area_id)).first()
                        except (ValueError, TypeError):
                            # Ignore if assignedAreaId is an old legacy Firestore string that can't be cast to int
                            pass

                # Create a new user dynamically
                # Generate a safe fallback username if one isn't available
                username = email.split('@')[0] if email else f"user_{uid[:8]}"
                
                # Handle unique username constraint
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = User.objects.create(
                    firebase_uid=uid,
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone_number,
                    user_type=user_type,
                    assigned_area=assigned_area
                )
                user.set_unusable_password() # They use Firebase auth
                user.save()
                
        return user
    except Exception as e:
        print(f"Firebase token verification failed: {e}")
        return None
