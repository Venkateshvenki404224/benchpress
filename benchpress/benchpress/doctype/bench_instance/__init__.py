import hashlib


def get_instance_id(email, lab_id):
	return hashlib.md5((email + lab_id).encode()).hexdigest()
