package com.viscane.offline;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class OfflineCalculatorTest {
    @Test public void matchesExpectedEstimateForManualAssessment() {
        OfflineCalculator.Result result = OfflineCalculator.calculate(
                0, 1.5, 1, 1, 1, 1, false, 2);
        assertEquals(1.836, result.lkgPerTon, 1e-9);
        assertEquals(322.65, result.totalTons, 1e-9);
        assertEquals(592.3854, result.totalLkg, 1e-8);
    }

    @Test public void rejectsNonPositiveArea() {
        assertThrows(IllegalArgumentException.class, () -> OfflineCalculator.calculate(
                0, 0, 1, 1, 1, 1, false, 0));
    }
}