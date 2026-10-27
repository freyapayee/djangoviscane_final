package com.viscane.offline

/** The complete-input branch of core.services.generate_recommendations, using bundled rule text. */
data class OfflineRecommendation(val category: String, val title: String, val detail: String)

object OfflineRecommendations {
    fun generate(variety: Int, hectares: Double, plowing: Int, weeding: Int, fertilizer: Int, stage: Int,
                 infected: Boolean, maturity: Int, estimate: OfflineCalculator.Result): List<OfflineRecommendation> {
        require(variety in OfflineRules.VARIETIES.indices)
        require(plowing in 1..3 && weeding in 1..3 && fertilizer in 1..3 && stage in 1..3 && maturity in 0..3)
        val name = OfflineRules.VARIETIES[variety]
        val recommendations = mutableListOf<OfflineRecommendation>()
        fun add(category: String, title: String, detail: String) {
            recommendations += OfflineRecommendation(category, title, detail)
        }
        when (maturity) {
            1 -> add("Harvest Directives", "Delay cutting for sucrose accumulation",
                "Real-time harvest directive: Not Mature classification indicates stalks should not be cut yet. Delay harvest to allow optimal sucrose accumulation before scheduling transport.")
            2 -> add("Harvest Directives", "Finalize immediate harvest logistics",
                "Real-time harvest directive: Mature classification indicates harvest-ready stalks. Proceed with immediate cutting and finalize hauling/transport coordination.")
            3 -> add("Harvest Directives", "Expedite harvest to prevent further yield loss",
                "Real-time harvest directive: Over Mature classification requires urgent cutting. Expedite harvest to mitigate further yield degradation caused by sucrose inversion.")
        }
        // The server compares predicted total LKG with the unadjusted variety and stage baseline.
        val baseline = OfflineRules.LKG[variety][stage - 1] * OfflineRules.TONS[variety][stage - 1]
        val lowLkg = baseline > 0 && estimate.totalLkg / (baseline * hectares) < 0.85
        for ((value, label, category) in listOf(
            Triple(plowing, "plowing", "Plowing Guidance"),
            Triple(weeding, "weeding", "Weeding Guidance"),
            Triple(fertilizer, "fertilizer", "Fertilizer Guidance"))) {
            if (value < 2) add(category, "Increase $label from 1 to at least 2",
                "Low input level is pulling down predicted LKG.")
        }
        if (infected) add("Pest and Disease", "RSSI infected: apply PHILSURIN control protocol",
            "Conduct weekly monitoring, especially lower leaf areas, and immediately remove and burn infested leaves to prevent spread. Effective chemical options include Carbofuran, Phenthoate, Dinotefuran, Thiamethoxam, Pymetrozine, and Buprofezin. Report suspected infestations to PHILSURIN, DA, or SRA, and adopt integrated pest management using monitoring, physical removal, and chemical or biological interventions.")
        if (lowLkg) add("Fertilizer Guidance", "Follow $fertilizer-time fertilizer schedule for $name",
            OfflineRules.FERTILIZER[variety][fertilizer - 1])
        for (choice in (fertilizer + 1)..3) add("Fertilizer Guidance",
            "Consider $choice-time fertilizer application for $name", OfflineRules.FERTILIZER[variety][choice - 1])
        if (lowLkg) add("Weeding Guidance", "Follow $weeding-time weeding schedule for $name",
            OfflineRules.WEEDING[variety][weeding - 1])
        for (choice in (weeding + 1)..3) add("Weeding Guidance",
            "Consider $choice-time weeding for $name", OfflineRules.WEEDING[variety][choice - 1])
        if (lowLkg) add("Plowing Guidance", "Follow $plowing-time plowing schedule for $name",
            OfflineRules.PLOWING[variety][plowing - 1])
        if (variety == 1 && stage > 1) add("Plowing Guidance", "For VMC 84-947 ratoon, avoid plowing",
            "Use stubble shaving and inter-row cultivation (off-barring) to protect ratoon shoots.")
        else for (choice in (plowing + 1)..3) add("Plowing Guidance",
            "Consider $choice-time plowing for $name", OfflineRules.PLOWING[variety][choice - 1])
        if (recommendations.isEmpty()) add("General", "Maintain current agronomic practices",
            "Current inputs support baseline-level yield.")
        return recommendations
    }
}
