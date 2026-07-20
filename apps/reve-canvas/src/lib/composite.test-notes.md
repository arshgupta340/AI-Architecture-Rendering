# Masked-delta composite verification

The brief restricts this workstream to the library, this note, and the dev route, so
the dev route is the executable browser verification surface rather than a separate
test harness.

## Expected cases

1. **Fixture composition:** `/sample.jpg` plus the mock Travertine render produces a
   PNG at `1400 x 611`, shows the changed House 1 region, and reports a drift score
   below `0.05` outside the generated mask.
2. **Source preservation:** pixels where mask alpha is below `0.05` are copied from
   the original image; the composite view therefore has no render pixels outside the
   selected region.
3. **Resolution mismatch:** the fixture render is cover-fit and center-cropped onto
   the original canvas before composition; output dimensions always come from the
   original data URL.
4. **Edge bbox:** normalized rectangles are clipped to the canvas. A rectangle
   touching an image edge remains opaque through that edge rather than fading to
   transparency beyond the image.
5. **Overlapping boxes:** each padded rectangle contributes its own alpha and their
   union uses the maximum alpha, so overlapping regions never create a dim seam.
6. **Feather:** the mask has a linear `2 * featherPx` transition around each padded
   rectangle boundary, including the pad; the same mask is returned for inspection.

## Manual browser check

Run `npm run dev`, open `/dev/composite`, and confirm the status row reports the
original dimensions, a drift score below `0.05`, and `MOCK · $0`. Cycle through
Original, Render, Composite, Mask, and Diff heatmap. The mask should show a soft
edge and the composite should have no visible rectangular seam.
