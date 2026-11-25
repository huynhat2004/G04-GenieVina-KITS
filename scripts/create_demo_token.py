#!/usr/bin/env python3
"""Local CLI helper only; member login/logout belongs to member D."""
import argparse
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--member-id', type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    secret = os.environ.get('JWT_SECRET', '')
    if len(secret.encode()) < 32:
        parser.error('Set JWT_SECRET to at least 32 bytes in .env or the environment')
    now = datetime.now(timezone.utc)
    print(jwt.encode({'sub': str(args.member_id), 'iat': now, 'exp': now + timedelta(minutes=30)},
                     secret, algorithm='HS256'))


if __name__ == '__main__':
    main()
