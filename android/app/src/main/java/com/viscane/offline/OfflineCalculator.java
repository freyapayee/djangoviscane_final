package com.viscane.offline;

/** Numeric port of core.services.predict_variety_metrics for the farmer calculator.
 * Variety and maturity are manually entered; this class performs no image inference.
 */
public final class OfflineCalculator {
    private OfflineCalculator() {}

    public static final class Result {
        public final double lkgPerTon, totalTons, totalLkg, multiplier;
        private Result(double lkgPerTon, double totalTons, double multiplier) {
            this.lkgPerTon = lkgPerTon;
            this.totalTons = totalTons;
            this.totalLkg = lkgPerTon * totalTons;
            this.multiplier = multiplier;
        }
    }

    /** maturity: 0 = unknown, 1 = not mature, 2 = mature, 3 = over mature. */
    public static Result calculate(int variety, double hectares, int plowing,
            int weeding, int fertilizer, int stage, boolean infected, int maturity) {
        if (variety < 0 || variety >= OfflineRules.VARIETIES.length)
            throw new IllegalArgumentException("Select a supported variety.");
        if (Double.isNaN(hectares) || Double.isInfinite(hectares) || hectares <= 0)
            throw new IllegalArgumentException("Enter a positive, finite area in hectares.");
        for (int count : new int[] {plowing, weeding, fertilizer, stage}) {
            if (count < 1 || count > 3)
                throw new IllegalArgumentException("Counts and crop stage must be 1, 2 or 3.");
        }
        if (maturity < 0 || maturity > 3)
            throw new IllegalArgumentException("Select a supported maturity status.");
        double[] features = {infected ? 1 : 0, weeding, fertilizer, stage, plowing};
        double penalty = 0;
        // The website uses negative contributions only for yield, not the full sum.
        for (int i = 0; i < features.length; i++)
            penalty += Math.min(0, features[i] * OfflineRules.WEIGHTS[i]);
        double multiplier = Math.max(0, 1 + penalty + OfflineRules.MATURITY[variety][maturity]);
        double baselineLkg = OfflineRules.LKG[variety][stage - 1];
        double baselineTons = OfflineRules.TONS[variety][stage - 1] * hectares;
        double lkg = Math.max(0, Math.min(baselineLkg, baselineLkg * multiplier));
        double tons = Math.max(0, Math.min(baselineTons, baselineTons * multiplier));
        Result result = new Result(lkg, tons, multiplier);
        if (Double.isNaN(result.totalTons) || Double.isInfinite(result.totalTons)
                || Double.isNaN(result.totalLkg) || Double.isInfinite(result.totalLkg))
            throw new IllegalArgumentException("Area is too large to calculate.");
        return result;
    }
}
