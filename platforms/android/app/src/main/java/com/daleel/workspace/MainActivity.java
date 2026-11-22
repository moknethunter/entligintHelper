package com.daleel.workspace;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int PICK_DATABASE = 1;
    private static final long MAX_DATABASE_BYTES = 128L * 1024 * 1024;
    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor();
    private Button demo;
    private Button importData;
    private TextView status;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        layout.setPadding(32, 72, 32, 36);
        layout.setBackgroundColor(Color.rgb(243, 245, 240));

        TextView title = new TextView(this);
        title.setText(R.string.workspace_title);
        title.setTextSize(34);
        layout.addView(title);

        TextView help = new TextView(this);
        help.setText(R.string.workspace_help);
        help.setTextSize(17);
        help.setPadding(0, 4, 0, 24);
        layout.addView(help);

        demo = new Button(this);
        demo.setText(R.string.demo);
        demo.setOnClickListener(view -> launch(null));
        layout.addView(demo);

        importData = new Button(this);
        importData.setText(R.string.import_data);
        importData.setOnClickListener(view -> chooseDatabase());
        layout.addView(importData);

        status = new TextView(this);
        status.setPadding(0, 16, 0, 0);
        layout.addView(status);
        setContentView(layout);
    }

    private void chooseDatabase() {
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("*/*");
        picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivityForResult(picker, PICK_DATABASE);
        } catch (ActivityNotFoundException error) {
            status.setText(R.string.failed);
        }
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK_DATABASE && result == RESULT_OK && data != null && data.getData() != null) {
            launch(data.getData());
        }
    }

    private void launch(Uri document) {
        demo.setEnabled(false);
        importData.setEnabled(false);
        status.setText(R.string.loading);
        WORKER.execute(() -> {
            File database = null;
            try {
                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(getApplicationContext()));
                }
                if (document != null) {
                    database = File.createTempFile("import-", ".db", getCacheDir());
                    copyDatabase(document, database);
                }
                String url = Python.getInstance().getModule("mobile").callAttr(
                        "launch", getFilesDir().getAbsolutePath(), getCacheDir().getAbsolutePath(),
                        database == null ? "" : database.getAbsolutePath(), getString(R.string.import_label)
                ).toString();
                runOnUiThread(() -> showBrowser(url));
            } catch (Exception error) {
                if (database != null) database.delete();
                runOnUiThread(() -> finishLoading(R.string.failed));
            }
        });
    }

    private void copyDatabase(Uri document, File database) throws IOException {
        try (InputStream input = getContentResolver().openInputStream(document);
             OutputStream output = new java.io.FileOutputStream(database)) {
            if (input == null) throw new IOException("Missing source stream");
            byte[] buffer = new byte[32 * 1024];
            long count = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                count += read;
                if (count > MAX_DATABASE_BYTES) throw new IOException("Source exceeds limit");
                output.write(buffer, 0, read);
            }
        }
    }

    private void showBrowser(String url) {
        if (isFinishing() || isDestroyed()) return;
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            finishLoading(R.string.ready);
        } catch (ActivityNotFoundException error) {
            finishLoading(R.string.no_browser);
        }
    }

    private void finishLoading(int message) {
        demo.setEnabled(true);
        importData.setEnabled(true);
        status.setText(message);
    }
}
