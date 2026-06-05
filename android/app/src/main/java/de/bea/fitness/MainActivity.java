package de.bea.fitness;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebChromeClient.FileChooserParams;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST_CODE = 42;
    private static final String PREFS_NAME = "bea_android";
    private static final String PREF_SERVER_URL = "server_url";
    private static final String DEFAULT_SERVER_URL = BuildConfig.DEFAULT_SERVER_URL;

    private LinearLayout browserLayout;
    private ScrollView setupView;
    private WebView webView;
    private TextView serverLabel;
    private ProgressBar progressBar;
    private SharedPreferences preferences;
    private ValueCallback<Uri[]> fileUploadCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        FrameLayout root = new FrameLayout(this);
        setupView = buildSetupView();
        browserLayout = buildBrowserLayout();
        root.addView(browserLayout);
        root.addView(setupView);
        setContentView(root);

        String serverUrl = preferences.getString(PREF_SERVER_URL, "");
        if (serverUrl == null || serverUrl.trim().isEmpty()) {
            showSetup();
        } else {
            showBrowser(serverUrl);
        }
    }

    private ScrollView buildSetupView() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.setBackgroundColor(Color.rgb(248, 251, 255));

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setPadding(dp(24), dp(32), dp(24), dp(32));
        scrollView.addView(
            content,
            new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
            )
        );

        TextView logo = new TextView(this);
        logo.setText("Bea");
        logo.setTextColor(Color.rgb(23, 32, 51));
        logo.setTextSize(34);
        logo.setGravity(Gravity.CENTER);
        logo.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        content.addView(logo, matchWrap());

        TextView intro = new TextView(this);
        intro.setText("Verbinde die Android-App mit deinem Bea-Server auf dem Raspberry Pi.");
        intro.setTextColor(Color.rgb(69, 82, 104));
        intro.setTextSize(17);
        intro.setGravity(Gravity.CENTER);
        intro.setPadding(0, dp(16), 0, dp(16));
        content.addView(intro, matchWrap());

        EditText serverInput = new EditText(this);
        serverInput.setSingleLine(true);
        serverInput.setHint(DEFAULT_SERVER_URL);
        serverInput.setText(preferences.getString(PREF_SERVER_URL, DEFAULT_SERVER_URL));
        serverInput.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        content.addView(serverInput, matchWrap());

        TextView hint = new TextView(this);
        hint.setText(BuildConfig.ALLOW_CLEARTEXT_SERVER
            ? "Nutze nicht localhost, sondern die Adresse deines Raspberry Pi, z.B. http://raspidiss.local:8010 oder http://192.168.178.40:8010."
            : "Diese Release-Version erwartet HTTPS, z.B. https://bea.example.de oder eine VPN-Adresse mit gültigem Zertifikat.");
        hint.setTextColor(Color.rgb(100, 116, 139));
        hint.setTextSize(14);
        hint.setPadding(0, dp(10), 0, dp(18));
        content.addView(hint, matchWrap());

        Button connectButton = new Button(this);
        connectButton.setText("Verbinden");
        connectButton.setAllCaps(false);
        connectButton.setOnClickListener(view -> {
            String rawServerUrl = serverInput.getText().toString();
            String normalized = normalizeServerUrl(rawServerUrl);
            if (normalized.isEmpty()) {
                Toast.makeText(this, "Bitte Server-Adresse eintragen.", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!BuildConfig.ALLOW_CLEARTEXT_SERVER && normalized.toLowerCase().startsWith("http://")) {
                Toast.makeText(this, "Für diese App-Version ist HTTPS erforderlich.", Toast.LENGTH_LONG).show();
                return;
            }
            preferences.edit().putString(PREF_SERVER_URL, normalized).apply();
            showBrowser(normalized);
        });
        content.addView(connectButton, matchWrap());

        LinearLayout legalLinks = new LinearLayout(this);
        legalLinks.setOrientation(LinearLayout.VERTICAL);
        legalLinks.setGravity(Gravity.CENTER);
        content.addView(legalLinks, matchWrap());

        Button privacyButton = new Button(this);
        privacyButton.setText("Datenschutz");
        privacyButton.setAllCaps(false);
        privacyButton.setOnClickListener(view -> openServerPage(serverInput, "/datenschutz"));
        legalLinks.addView(privacyButton, matchWrap());

        Button healthButton = new Button(this);
        healthButton.setText("Gesundheit");
        healthButton.setAllCaps(false);
        healthButton.setOnClickListener(view -> openServerPage(serverInput, "/gesundheitshinweis"));
        legalLinks.addView(healthButton, matchWrap());

        Button deleteAccountButton = new Button(this);
        deleteAccountButton.setText("Konto löschen");
        deleteAccountButton.setAllCaps(false);
        deleteAccountButton.setOnClickListener(view -> openServerPage(serverInput, "/konto-loeschung"));
        legalLinks.addView(deleteAccountButton, matchWrap());

        return scrollView;
    }

    private LinearLayout buildBrowserLayout() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.WHITE);

        LinearLayout topbar = new LinearLayout(this);
        topbar.setOrientation(LinearLayout.HORIZONTAL);
        topbar.setGravity(Gravity.CENTER_VERTICAL);
        topbar.setPadding(dp(10), dp(8), dp(10), dp(8));
        topbar.setBackgroundColor(Color.WHITE);
        layout.addView(topbar, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        TextView title = new TextView(this);
        title.setText("Bea");
        title.setTextColor(Color.rgb(23, 32, 51));
        title.setTextSize(20);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        topbar.addView(title, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        serverLabel = new TextView(this);
        serverLabel.setTextColor(Color.rgb(100, 116, 139));
        serverLabel.setTextSize(12);
        serverLabel.setSingleLine(true);
        LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        labelParams.setMargins(dp(10), 0, dp(10), 0);
        topbar.addView(serverLabel, labelParams);

        Button reloadButton = new Button(this);
        reloadButton.setText("Neu laden");
        reloadButton.setAllCaps(false);
        reloadButton.setOnClickListener(view -> webView.reload());
        topbar.addView(reloadButton, smallButtonParams());

        Button serverButton = new Button(this);
        serverButton.setText("Server");
        serverButton.setAllCaps(false);
        serverButton.setOnClickListener(view -> showSetup());
        topbar.addView(serverButton, smallButtonParams());

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        layout.addView(progressBar, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            dp(3)
        ));

        webView = new WebView(this);
        configureWebView(webView);
        layout.addView(webView, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        return layout;
    }

    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(view, true);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);

        view.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleExternalUrl(request.getUrl());
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    Toast.makeText(MainActivity.this, "Bea-Server ist nicht erreichbar.", Toast.LENGTH_LONG).show();
                }
            }
        });

        view.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
                progressBar.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public boolean onShowFileChooser(
                WebView webView,
                ValueCallback<Uri[]> filePathCallback,
                FileChooserParams fileChooserParams
            ) {
                if (fileUploadCallback != null) {
                    fileUploadCallback.onReceiveValue(null);
                }
                fileUploadCallback = filePathCallback;

                Intent contentIntent = new Intent(Intent.ACTION_GET_CONTENT);
                contentIntent.addCategory(Intent.CATEGORY_OPENABLE);
                contentIntent.setType("image/*");
                contentIntent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, fileChooserParams.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);

                Intent chooser = Intent.createChooser(contentIntent, "Foto auswählen");
                try {
                    startActivityForResult(chooser, FILE_CHOOSER_REQUEST_CODE);
                } catch (ActivityNotFoundException exc) {
                    fileUploadCallback = null;
                    Toast.makeText(MainActivity.this, "Keine Fotoauswahl verfügbar.", Toast.LENGTH_LONG).show();
                    return false;
                }
                return true;
            }
        });
    }

    private boolean handleExternalUrl(Uri uri) {
        String scheme = uri.getScheme();
        if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
            return false;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException exc) {
            Toast.makeText(this, "Link kann nicht geöffnet werden.", Toast.LENGTH_SHORT).show();
        }
        return true;
    }

    private void showSetup() {
        browserLayout.setVisibility(View.GONE);
        setupView.setVisibility(View.VISIBLE);
    }

    private void showBrowser(String serverUrl) {
        String normalized = normalizeServerUrl(serverUrl);
        if (!BuildConfig.ALLOW_CLEARTEXT_SERVER && normalized.toLowerCase().startsWith("http://")) {
            Toast.makeText(this, "Für diese App-Version ist HTTPS erforderlich.", Toast.LENGTH_LONG).show();
            showSetup();
            return;
        }
        setupView.setVisibility(View.GONE);
        browserLayout.setVisibility(View.VISIBLE);
        serverLabel.setText(normalized);
        webView.loadUrl(normalized);
    }

    private void openServerPage(EditText serverInput, String path) {
        String normalized = normalizeServerUrl(serverInput.getText().toString());
        if (normalized.isEmpty()) {
            Toast.makeText(this, "Bitte Server-Adresse eintragen.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!BuildConfig.ALLOW_CLEARTEXT_SERVER && normalized.toLowerCase().startsWith("http://")) {
            Toast.makeText(this, "Für diese App-Version ist HTTPS erforderlich.", Toast.LENGTH_LONG).show();
            return;
        }
        showBrowser(normalized + path);
    }

    private String normalizeServerUrl(String rawValue) {
        String value = rawValue == null ? "" : rawValue.trim();
        if (value.isEmpty()) {
            return "";
        }
        if (!value.matches("^[A-Za-z][A-Za-z0-9+.-]*://.*")) {
            value = (BuildConfig.ALLOW_CLEARTEXT_SERVER ? "http://" : "https://") + value;
        }
        int schemeEnd = value.indexOf("://");
        int minLength = schemeEnd >= 0 ? schemeEnd + 4 : "http://x".length();
        while (value.endsWith("/") && value.length() > minLength) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST_CODE || fileUploadCallback == null) {
            return;
        }

        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                results = new Uri[count];
                for (int index = 0; index < count; index++) {
                    results[index] = data.getClipData().getItemAt(index).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[] { data.getData() };
            }
        }

        fileUploadCallback.onReceiveValue(results);
        fileUploadCallback = null;
    }

    @Override
    public void onBackPressed() {
        if (setupView.getVisibility() == View.VISIBLE) {
            super.onBackPressed();
            return;
        }
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    private LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, dp(6), 0, dp(6));
        return params;
    }

    private LinearLayout.LayoutParams smallButtonParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(dp(4), 0, 0, 0);
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
