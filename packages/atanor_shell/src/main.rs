//! ATANOR Shell — M0 scaffold.
//!
//! Proves the native-render pipeline the whole 2b plan stands on: a window,
//! a wgpu surface, and a deep-space clear at 60fps. M1 swaps winit for
//! smithay's DRM/TTY backend and starts compositing real Wayland clients;
//! M2 replaces the clear with the SPLATRA particle field (point sprites,
//! engine-state-driven morphing). No browser anywhere in this future.

use std::sync::Arc;

use winit::{
    event::{Event, WindowEvent},
    event_loop::EventLoop,
    window::WindowBuilder,
};

const DEEP_SPACE: wgpu::Color = wgpu::Color { r: 0.0196, g: 0.0275, b: 0.0392, a: 1.0 };

fn main() {
    env_logger::init();
    let event_loop = EventLoop::new().expect("event loop");
    // Arc: the surface borrows the window AND the event-loop closure owns it —
    // shared ownership is the honest shape here (E0505 caught by the first build)
    let window = Arc::new(
        WindowBuilder::new()
            .with_title("ATANOR Shell (M0)")
            .build(&event_loop)
            .expect("window"),
    );

    let instance = wgpu::Instance::default();
    let surface = instance.create_surface(window.clone()).expect("surface");
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        compatible_surface: Some(&surface),
        ..Default::default()
    }))
    .expect("adapter");
    let (device, queue) = pollster::block_on(adapter.request_device(&Default::default(), None))
        .expect("device");

    let size = window.inner_size();
    let mut config = surface
        .get_default_config(&adapter, size.width.max(1), size.height.max(1))
        .expect("surface config");
    surface.configure(&device, &config);

    log::info!("ATANOR Shell M0 up — adapter: {:?}", adapter.get_info().name);

    event_loop
        .run(move |event, elwt| match event {
            Event::WindowEvent { event, .. } => match event {
                WindowEvent::CloseRequested => elwt.exit(),
                WindowEvent::Resized(new_size) => {
                    config.width = new_size.width.max(1);
                    config.height = new_size.height.max(1);
                    surface.configure(&device, &config);
                }
                WindowEvent::RedrawRequested => {
                    let frame = match surface.get_current_texture() {
                        Ok(f) => f,
                        Err(_) => {
                            surface.configure(&device, &config);
                            return;
                        }
                    };
                    let view = frame.texture.create_view(&Default::default());
                    let mut encoder = device.create_command_encoder(&Default::default());
                    {
                        let _pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                            label: Some("deep-space-clear"),
                            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                                view: &view,
                                resolve_target: None,
                                ops: wgpu::Operations {
                                    load: wgpu::LoadOp::Clear(DEEP_SPACE),
                                    store: wgpu::StoreOp::Store,
                                },
                            })],
                            ..Default::default()
                        });
                        // M2: SPLATRA point-sprite pass lands here.
                    }
                    queue.submit(Some(encoder.finish()));
                    frame.present();
                    window.request_redraw();
                }
                _ => {}
            },
            _ => {}
        })
        .expect("run");
}
