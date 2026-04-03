import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiService {

  static const baseUrl = "https://skinapp.onrender.com";
  static const _timeout = Duration(seconds: 60); // handles Render cold start

  // 🔐 LOGIN
  static Future login(String username, String password) async {
    try {
      var res = await http.post(
        Uri.parse("$baseUrl/login"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("LOGIN ERROR: $e");
      return {"error": "Server unreachable. Please wait and try again."};
    }
  }

  // 📝 REGISTER
  static Future register(String username, String password) async {
    try {
      var res = await http.post(
        Uri.parse("$baseUrl/register"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("REGISTER ERROR: $e");
      return {"error": "Server unreachable. Please wait and try again."};
    }
  }

  // 🔑 CHANGE PASSWORD
  static Future changePassword(String username, String password) async {
    try {
      var res = await http.put(
        Uri.parse("$baseUrl/change_password"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("CHANGE PASSWORD ERROR: $e");
      return {"error": "Password update failed."};
    }
  }

  // 🤖 PREDICT
  static Future predictImage(File image, String username) async {
    try {
      var request = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/predict"),
      );
      request.fields["username"] = username;
      request.files.add(
        await http.MultipartFile.fromPath("image", image.path),
      );
      var response = await request.send().timeout(_timeout);
      var res = await http.Response.fromStream(response);
      return jsonDecode(res.body);
    } catch (e) {
      print("PREDICT ERROR: $e");
      return {"error": "Prediction failed. Please try again."};
    }
  }

  // 📜 USER HISTORY (filtered by username)
  static Future<List> getHistory(String username) async {
    try {
      var res = await http.get(
        Uri.parse("$baseUrl/history?username=$username"),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("HISTORY ERROR: $e");
      return [];
    }
  }

  // ─── ADMIN ────────────────────────────────────────────────────────────────

  // 👥 GET ALL USERS
  static Future<List> getUsers() async {
    try {
      var res = await http.get(
        Uri.parse("$baseUrl/admin/users"),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("GET USERS ERROR: $e");
      return [];
    }
  }

  // 🗑️ DELETE USER
  static Future deleteUser(String username) async {
    try {
      var res = await http.delete(
        Uri.parse("$baseUrl/admin/delete_user?username=$username"),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("DELETE USER ERROR: $e");
      return {"error": "Delete failed."};
    }
  }

  // ⬆️ PROMOTE USER
  static Future promoteUser(String username) async {
    try {
      var res = await http.put(
        Uri.parse("$baseUrl/admin/promote_user"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username}),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("PROMOTE USER ERROR: $e");
      return {"error": "Promote failed."};
    }
  }

  // ⬇️ DEMOTE USER
  static Future demoteUser(String username) async {
    try {
      var res = await http.put(
        Uri.parse("$baseUrl/admin/demote_user"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username}),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("DEMOTE USER ERROR: $e");
      return {"error": "Demote failed."};
    }
  }

  // 📊 ADMIN HISTORY
  static Future<List> getAdminHistory() async {
    try {
      var res = await http.get(
        Uri.parse("$baseUrl/admin/history"),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("ADMIN HISTORY ERROR: $e");
      return [];
    }
  }

  // 🦠 GET DISEASES
  static Future<List> getDiseases() async {
    try {
      var res = await http.get(
        Uri.parse("$baseUrl/admin/diseases"),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("GET DISEASES ERROR: $e");
      return [];
    }
  }

  // ✏️ UPDATE DISEASE
  static Future updateDisease(Map data) async {
    try {
      var res = await http.put(
        Uri.parse("$baseUrl/admin/update_disease"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(data),
      ).timeout(_timeout);
      return jsonDecode(res.body);
    } catch (e) {
      print("UPDATE DISEASE ERROR: $e");
      return {"error": "Update failed."};
    }
  }
}