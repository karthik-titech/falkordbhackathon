import FalkorDBCanvas from "./canvas.js";
import type React from "react";
import type { CanvasDimension, CanvasRenderMode, LayoutMode, LayoutDirection, HierarchyDirection, RadialDirection, LayoutOptions, HierarchyLayoutOptions, RadialLayoutOptions, ForceLayoutOptions, NodeStyleConfig, LinkStyleConfig, SimulationConfig, InteractionConfig, EventHandlers } from "./canvas-types.js";
declare global {
    interface HTMLElementTagNameMap {
        "falkordb-canvas": FalkorDBCanvas;
    }
    namespace JSX {
        interface IntrinsicElements {
            "falkordb-canvas": React.DetailedHTMLProps<React.HTMLAttributes<FalkorDBCanvas> & {
                'node-mode'?: CanvasRenderMode;
                'link-mode'?: CanvasRenderMode;
            }, FalkorDBCanvas>;
        }
    }
}
export { FalkorDBCanvas as default, FalkorDBCanvas };
export type { CanvasDimension, CanvasRenderMode, LayoutMode, LayoutDirection, HierarchyDirection, RadialDirection, LayoutOptions, HierarchyLayoutOptions, RadialLayoutOptions, ForceLayoutOptions, NodeStyleConfig, LinkStyleConfig, SimulationConfig, InteractionConfig, EventHandlers, };
export type { ForceGraphConfig, LargeGraphConfig, GraphNode, GraphLink, GraphData, Node, NodeShape, Link, Data, ViewportState, ForceGraphInstance, Transform, } from "./canvas-types.js";
export type { WorldBounds } from "./canvas.js";
export { NODE_SIZE, LINK_WIDTH, LINK_FONT_SIZE, ARROW_SIZE, dataToGraphData, graphDataToData, getContrastTextColor, getNodeDisplayText, getNodeDisplayKey, wrapTextForCircularNode, } from "./canvas-utils.js";
export { getDagMode, isForceLayout, getDagLevelDistance, pinAllNodes, unpinAllNodes, } from "./layouts.js";
//# sourceMappingURL=index.d.ts.map