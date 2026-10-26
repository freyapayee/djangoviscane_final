package com.viscane.offline;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Device-local records only. There is no Django sync endpoint in this starter. */
final class AssessmentStore extends SQLiteOpenHelper {
    AssessmentStore(Context context) { super(context, "assessments.db", null, 1); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE assessments (id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, payload TEXT NOT NULL)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        throw new IllegalStateException("A non-destructive migration is required.");
    }

    void save(JSONObject payload) throws JSONException {
        ContentValues row = new ContentValues();
        row.put("id", payload.getString("id"));
        row.put("created_at", payload.getLong("created_at"));
        row.put("payload", payload.toString());
        getWritableDatabase().insertOrThrow("assessments", null, row);
    }

    JSONArray records(int limit) throws JSONException {
        JSONArray records = new JSONArray();
        try (Cursor cursor = getReadableDatabase().query("assessments",
                new String[] {"payload"}, null, null, null, null, "created_at DESC, id DESC",
                limit > 0 ? Integer.toString(limit) : null)) {
            while (cursor.moveToNext()) records.put(new JSONObject(cursor.getString(0)));
        }
        return records;
    }
}
