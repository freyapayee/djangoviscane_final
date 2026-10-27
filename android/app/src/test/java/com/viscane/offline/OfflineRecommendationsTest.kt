package com.viscane.offline

import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineRecommendationsTest {
    @Test fun harvestAndAgronomicGuidanceWorkWithoutServerData() {
        val estimate = OfflineCalculator.calculate(0, 1.5, 1, 1, 1, 1, true, 2)
        val titles = OfflineRecommendations.generate(0, 1.5, 1, 1, 1, 1, true, 2, estimate)
            .map { it.title }
        assertTrue(titles.contains("Finalize immediate harvest logistics"))
        assertTrue(titles.contains("RSSI infected: apply PHILSURIN control protocol"))
        assertTrue(titles.contains("Consider 2-time fertilizer application for VMC 84-524"))
    }

    @Test fun ratoonGuidanceAvoidsPlowingForVmc947() {
        val estimate = OfflineCalculator.calculate(1, 1.0, 1, 2, 2, 2, false, 0)
        val titles = OfflineRecommendations.generate(1, 1.0, 1, 2, 2, 2, false, 0, estimate)
            .map { it.title }
        assertTrue(titles.contains("For VMC 84-947 ratoon, avoid plowing"))
    }
}
