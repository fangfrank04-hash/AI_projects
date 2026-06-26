package com.ccdc.proposal.util;

import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

@Component
public class DateUtil {

    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    public LocalDate parse(String dateStr) {
        return LocalDate.parse(dateStr, FORMATTER);
    }

    public String format(LocalDate date) {
        return date.format(FORMATTER);
    }

    public LocalDate addDays(LocalDate date, int days) {
        return date.plusDays(days);
    }
}
