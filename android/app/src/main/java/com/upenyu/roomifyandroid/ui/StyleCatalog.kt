package com.upenyu.roomifyandroid.ui

import com.upenyu.roomifyandroid.model.MaterialSpec
import com.upenyu.roomifyandroid.model.SceneManifest
import com.upenyu.roomifyandroid.model.SceneMaterials


data class DesignStyle(
    val id: String,
    val label: String,
    val description: String,
    val floor: String,
    val walls: String,
    val exterior: String,
    val accent: String,
)

object StyleCatalog {
    val styles = listOf(
        DesignStyle("modern", "Modern", "Warm timber, precise lines and restrained contrast.", "#B58A5A", "#EEEAE2", "#A8AAA6", "#32383A"),
        DesignStyle("contemporary", "Contemporary", "Layered neutrals and sculptural accents.", "#8B6C50", "#DDD8D0", "#8C918E", "#8A6C4B"),
        DesignStyle("farmhouse", "Farmhouse", "Natural oak, soft whites and practical rustic detail.", "#A8794C", "#F3EFE5", "#C8BCA8", "#71806B"),
        DesignStyle("mediterranean", "Mediterranean", "Terracotta, lime plaster and honey stone.", "#B8663E", "#EADCC4", "#C2A77E", "#315D73"),
        DesignStyle("scandinavian", "Scandinavian", "Pale timber, bright walls and calm function.", "#D5C7AD", "#F4F1E9", "#B7A98D", "#617B84"),
        DesignStyle("industrial", "Industrial", "Concrete, brick and blackened steel.", "#777A78", "#B7B4AD", "#774D3D", "#282C2E"),
        DesignStyle("traditional", "Traditional", "Rich timber, balanced proportions and timeless detail.", "#765035", "#E8DDC8", "#9E8A72", "#394E3E"),
        DesignStyle("craftsman", "Craftsman", "Quarter-sawn oak, stone and earthy colour.", "#805A38", "#D8C7AA", "#81776A", "#344A38"),
        DesignStyle("colonial", "Colonial", "Symmetry, cream walls and classic dark wood.", "#68412E", "#EADFCB", "#C7C0B2", "#435B72"),
        DesignStyle("ranch", "Ranch", "Relaxed horizontal planning and warm natural finishes.", "#9B7046", "#DFD1BA", "#8B7D68", "#9B5540"),
        DesignStyle("cape_cod", "Cape Cod", "Coastal whites, silvered timber and compact comfort.", "#C7B79B", "#F2F1EA", "#939994", "#304C65"),
        DesignStyle("tudor", "Tudor", "Dark oak, hand plaster and old brick.", "#523725", "#D8C9AD", "#68483B", "#673A35"),
        DesignStyle("victorian", "Victorian", "Decorative colour and polished timber.", "#6B452E", "#DED0BA", "#765044", "#315D5B"),
        DesignStyle("spanish", "Spanish", "Saltillo tile, limewash and wrought iron.", "#A95738", "#E9DEC7", "#D8CDBB", "#2F302E"),
        DesignStyle("minimalist", "Minimalist", "Quiet surfaces, precise lines and essential objects.", "#C9B99B", "#F2F0EA", "#A6A7A4", "#25282A"),
        DesignStyle("transitional", "Transitional", "Traditional warmth with modern simplicity.", "#9B7755", "#E1DAD0", "#AAA092", "#5F7180"),
        DesignStyle("coastal", "Coastal", "Airy whites, sand tones and ocean blue.", "#D2C4AA", "#F0F2ED", "#C8BBA3", "#4E7890"),
        DesignStyle("midcentury_modern", "Mid-century Modern", "Walnut, low profiles and optimistic colour.", "#704B32", "#DDD1BC", "#8B5D47", "#B58131"),
        DesignStyle("neo_classical", "Neo-classical", "Formal symmetry, pale stone and brass detail.", "#B9A98F", "#EEE9DF", "#B6AD9F", "#9A7A45"),
    )

    fun byId(id: String): DesignStyle = styles.firstOrNull { it.id == id } ?: styles.first()

    fun apply(scene: SceneManifest, styleId: String): SceneManifest {
        val style = byId(styleId)
        return scene.copy(
            materials = SceneMaterials(
                paletteName = style.label,
                floorGlobal = MaterialSpec("${style.label} floor", "wood", style.floor, roughness = 0.48),
                wallsGlobal = MaterialSpec("${style.label} walls", "plaster", style.walls, roughness = 0.8),
                exteriorWalls = MaterialSpec("${style.label} exterior", "stone", style.exterior, roughness = 0.84),
                accent = MaterialSpec("${style.label} accent", "paint", style.accent, roughness = 0.48),
                fixtureMetal = MaterialSpec("Architectural metal", "metal", "#A5A7AA", roughness = 0.24, metallic = 0.82, specular = 0.75),
            ),
        )
    }
}
