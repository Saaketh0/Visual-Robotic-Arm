#!/usr/bin/env python3

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


PKG_ROOT = Path(__file__).resolve().parents[1]
URDF_DIR = PKG_ROOT / "urdf"
MESH_DIR = PKG_ROOT / "meshes" / "stls"


class MeshReferenceTest(unittest.TestCase):
    def test_no_vendor_mesh_references_remain(self):
        for path in sorted(URDF_DIR.iterdir()):
            if not path.is_file():
                continue
            text = path.read_text()
            self.assertNotIn("xarm_description/meshes", text, path.as_posix())
            self.assertNotIn("model://xarm_description", text, path.as_posix())
            self.assertNotIn("package://xarm_description", text, path.as_posix())

    def test_referenced_meshes_exist_locally(self):
        expected = {
            "base.stl",
            "link2.stl",
            "link3.stl",
            "link4.stl",
            "link5.stl",
            "link6.stl",
        }
        actual = {path.name for path in MESH_DIR.glob("*.stl")}
        self.assertEqual(expected, actual)

    def test_sdf_relative_mesh_uris_resolve_to_existing_files(self):
        for sdf_name in ("xarm_mesh_control.sdf", "xarm_mesh_control.BEFORE_FIXED_BASE.sdf"):
            sdf_path = URDF_DIR / sdf_name
            root = ET.fromstring(sdf_path.read_text())
            mesh_uris = [uri.text for uri in root.findall(".//mesh/uri") if uri.text]
            self.assertTrue(mesh_uris, sdf_name)
            for uri in mesh_uris:
                if uri.startswith(("model://", "package://", "file://")):
                    continue
                resolved = (sdf_path.parent / uri).resolve()
                self.assertTrue(resolved.is_file(), f"{sdf_name}: missing mesh for {uri} -> {resolved}")


if __name__ == "__main__":
    unittest.main()
