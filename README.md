# FairSplit

AI-assisted restaurant bill splitting for Android, built with Expo and FastAPI. The mobile app scans a bill, the backend extracts structured items with Groq, and a deterministic Python engine calculates each person's settlement.

## Project layout

- `mobile/` — Expo Router React Native application.
- `backend/` — FastAPI API, Groq extraction service, and Decimal-based calculation engine.
- `supabase/migrations/` — PostgreSQL schema and Row Level Security policies.

## Run locally

1. Copy `backend/.env.example` to `backend/.env` and provide `GROQ_API_KEY`.
2. From `backend/`, create a Python virtual environment, install `requirements.txt`, then run `uvicorn app.main:app --reload`.
3. Copy `mobile/.env.example` to `mobile/.env` and set the API URL for your emulator or device.
4. From `mobile/`, run `npm install` followed by `npx expo start`.

The **Try Demo Bill** action works without a Groq key and exercises the complete allocation and split flow.

## Verify

```powershell
cd backend
pytest

cd ../mobile
npx tsc --noEmit
npx expo-doctor
```

## Android APK

Install and authenticate with EAS, then run:

```powershell
cd mobile
npx eas build --platform android --profile preview
```

The `preview` profile produces an installable APK. Before a real build, change the Android package identifier in `mobile/app.json` to one you control.

## Database

Use the Supabase CLI from the repository root to apply the migrations:

```powershell
supabase db push
```

Review the guest/session policies before enabling public production access; the current MVP policies support unauthenticated draft bills.
