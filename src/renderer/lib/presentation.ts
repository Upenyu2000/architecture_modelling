export type DesignStyle =
  | 'modern'
  | 'contemporary'
  | 'farmhouse'
  | 'mediterranean'
  | 'scandinavian'
  | 'industrial'
  | 'traditional'
  | 'craftsman'
  | 'colonial'
  | 'ranch'
  | 'cape_cod'
  | 'tudor'
  | 'victorian'
  | 'spanish'
  | 'minimalist'
  | 'transitional'
  | 'coastal'
  | 'midcentury_modern'
  | 'neo_classical';

export type RenderQuality = 'preview' | '1080p' | '4k';
export type PresentationEngine = 'auto' | 'blender';

export interface DesignStyleOption {
  value: DesignStyle;
  label: string;
  description: string;
}

export const DESIGN_STYLES: DesignStyleOption[] = [
  { value: 'modern', label: 'Modern', description: 'Clean geometry, warm timber and restrained contrast.' },
  { value: 'contemporary', label: 'Contemporary', description: 'Current forms, layered neutrals and sculptural accents.' },
  { value: 'farmhouse', label: 'Farmhouse', description: 'Natural oak, soft whites and practical rustic detailing.' },
  { value: 'mediterranean', label: 'Mediterranean', description: 'Sun-washed plaster, terracotta and warm stone.' },
  { value: 'scandinavian', label: 'Scandinavian', description: 'Pale timber, bright walls and calm functional furniture.' },
  { value: 'industrial', label: 'Industrial', description: 'Concrete, blackened steel, brick and honest structure.' },
  { value: 'traditional', label: 'Traditional', description: 'Balanced proportions, rich timber and timeless detailing.' },
  { value: 'craftsman', label: 'Craftsman', description: 'Hand-worked timber, earthy colour and built-in character.' },
  { value: 'colonial', label: 'Colonial', description: 'Symmetry, refined mouldings and classic dark wood.' },
  { value: 'ranch', label: 'Ranch', description: 'Relaxed horizontal planning, stone and warm natural finishes.' },
  { value: 'cape_cod', label: 'Cape Cod', description: 'Crisp white surfaces, coastal timber and compact comfort.' },
  { value: 'tudor', label: 'Tudor', description: 'Dark oak, plaster, stone and dramatic traditional contrast.' },
  { value: 'victorian', label: 'Victorian', description: 'Layered colour, decorative detail and polished timber.' },
  { value: 'spanish', label: 'Spanish', description: 'Terracotta, lime plaster, carved timber and iron accents.' },
  { value: 'minimalist', label: 'Minimalist', description: 'Quiet surfaces, precise lines and only essential objects.' },
  { value: 'transitional', label: 'Transitional', description: 'Traditional warmth balanced with modern simplicity.' },
  { value: 'coastal', label: 'Coastal', description: 'Airy whites, sand tones, light oak and ocean-inspired accents.' },
  { value: 'midcentury_modern', label: 'Mid-century Modern', description: 'Walnut, low-profile furniture and optimistic colour.' },
  { value: 'neo_classical', label: 'Neo-classical', description: 'Formal symmetry, pale stone and refined metallic detail.' },
];

export const PRESENTATION_RENDER_PROMPT = `
Generate a photorealistic 3D architectural presentation from the verified floor-plan geometry.

Create two coordinated outputs:
1. An orthographic top-down 3D view showing the complete layout with exact room proportions, walls, doors, windows and spatial relationships.
2. An eye-level interior perspective from a valid point inside the building, composed like a professional architectural photograph.

Apply the selected design style consistently across materials, colour palette, furniture finishes, lighting and decorative elements. Use realistic PBR surfaces for flooring, walls, fixtures and furnishings. Scale every object for its room and preserve circulation clearances. Optimise the dining area where required so the table and seating maintain practical flow. Use natural and artificial lighting to create depth while retaining architectural clarity.

Do not include source-plan text, labels, dimensions, annotations, logos or watermarks. Do not alter the verified building geometry or invent rooms. Produce high-quality renders suitable for architectural presentation.
`.trim();

export const styleLabel = (value: DesignStyle): string =>
  DESIGN_STYLES.find((style) => style.value === value)?.label ?? value.replaceAll('_', ' ');
