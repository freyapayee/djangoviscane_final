package com.viscane.app;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class FarmerNavigationOfflineTest {
    private final FarmerNavigation navigation = new FarmerNavigation("http://127.0.0.1:43127/");

    @Test public void allowsLocalRegistrationLoginAndHomeFlow() {
        assertTrue(navigation.allows("http://127.0.0.1:43127/"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/auth?mode=register&cover=done"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/auth/register-success"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/homepage"));
    }

    @Test public void allowsLocalFarmerFeaturesAndAssets() {
        assertTrue(navigation.allows("http://127.0.0.1:43127/scan/new"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/calculate"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/farmer/settings"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/static/css/design-system.css"));
        assertTrue(navigation.allows("http://127.0.0.1:43127/api/scan/predict?top_k=3"));
    }

    @Test public void keepsExternalSitesOutsideTheOfflineApp() {
        assertFalse(navigation.allows("https://viscane.app/homepage"));
        assertFalse(navigation.allows("http://localhost:43127/homepage"));
        assertFalse(navigation.allows("http://127.0.0.1:43127/admin"));
    }
}
