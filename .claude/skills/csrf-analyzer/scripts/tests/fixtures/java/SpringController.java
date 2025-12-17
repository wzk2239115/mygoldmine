package com.example.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;

@RestController
@RequestMapping("/api")
public class UserController {

    // Spring @PostMapping - state-changing operation
    @PostMapping("/user/update")
    public ResponseEntity<?> updateUser(@RequestBody UserRequest request) {
        // Update user data
        userService.updateUser(request);
        return ResponseEntity.ok("Updated");
    }

    // Spring @PutMapping - state-changing operation
    @PutMapping("/settings/{id}")
    public ResponseEntity<?> updateSettings(@PathVariable String id, @RequestBody Settings settings) {
        // Update settings without CSRF protection
        settingsService.update(id, settings);
        return ResponseEntity.ok("Settings updated");
    }

    // Spring @DeleteMapping - state-changing operation
    @DeleteMapping("/user/{id}")
    public ResponseEntity<?> deleteUser(@PathVariable String id) {
        userService.delete(id);
        return ResponseEntity.ok("Deleted");
    }

    // RequestMapping with POST method
    @RequestMapping(value = "/admin/action", method = RequestMethod.POST)
    public ResponseEntity<?> performAdminAction(@RequestBody AdminRequest req) {
        adminService.performAction(req);
        return ResponseEntity.ok("Action performed");
    }
}

// Configuration class with CSRF disabled
@Configuration
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
                .anyRequest().authenticated()
                .and()
            .csrf().disable();  // DANGEROUS: CSRF protection disabled
        return http.build();
    }
}
